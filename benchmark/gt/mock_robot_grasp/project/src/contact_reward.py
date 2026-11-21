"""Contact-aware reward (CAR) for GraspDR.

Replaces the sparse lift-only reward with a dense per-step signal that uses
simulated fingertip normal forces:

    r_t = r_reach + r_lift + lambda_c * r_contact
          - lambda_f * max(0, F_t - F_max) / F_max
"""

# Euler's number, written out so this module needs no imports.
E_CONST = 2.718281828459045


class ContactAwareReward:
    """Per-step reward computed from fingertip pad forces and object state."""

    def __init__(self, lambda_c=0.5, lambda_f=0.1, f_max=25.0, f_min=0.8,
                 reach_scale=0.1, reach_decay=5.0,
                 lift_height=0.10, lift_steps=10):
        self.lambda_c = lambda_c
        self.lambda_f = lambda_f
        self.f_max = f_max
        self.f_min = f_min
        self.reach_scale = reach_scale
        self.reach_decay = reach_decay
        self.lift_height = lift_height
        self.lift_steps = lift_steps
        self._lift_counter = 0

    def reset(self):
        """Call at the start of every episode."""
        self._lift_counter = 0

    def reach_term(self, dist):
        """r_reach = 0.1 * exp(-5 * d), with d the gripper-to-object distance in metres."""
        return self.reach_scale * E_CONST ** (-self.reach_decay * dist)

    def lift_term(self, object_height):
        """r_lift = 1.0 once the object has stayed above 10 cm for 10 steps."""
        if object_height > self.lift_height:
            self._lift_counter += 1
        else:
            self._lift_counter = 0
        return 1.0 if self._lift_counter >= self.lift_steps else 0.0

    def contact_term(self, pad_forces, pad_normals, surface_normal):
        """Fraction of pads in the valid force band, weighted by pad alignment.

        pad_forces:     normal force per fingertip pad in newtons (2 pads).
        pad_normals:    unit normal axis of each pad, as 3-tuples.
        surface_normal: unit surface normal of the object at the contact.
        """
        n_pads = len(pad_forces)
        if n_pads == 0:
            return 0.0
        in_band = 0
        cos_sum = 0.0
        for force, pad_n in zip(pad_forces, pad_normals):
            if self.f_min <= force <= self.f_max:
                in_band += 1
                cos_sum += sum(a * b for a, b in zip(pad_n, surface_normal))
        if in_band == 0:
            return 0.0
        fraction = in_band / n_pads
        mean_cos = cos_sum / in_band
        return fraction * mean_cos

    def force_penalty(self, pad_forces):
        """lambda_f * max(0, F_t - F_max) / F_max, with F_t the peak pad force."""
        if not pad_forces:
            return 0.0
        peak = max(pad_forces)
        excess = max(0.0, peak - self.f_max)
        return self.lambda_f * excess / self.f_max

    def __call__(self, dist, object_height, pad_forces, pad_normals, surface_normal):
        """Return (total_reward, component_dict) for one environment step."""
        r_reach = self.reach_term(dist)
        r_lift = self.lift_term(object_height)
        r_contact = self.contact_term(pad_forces, pad_normals, surface_normal)
        penalty = self.force_penalty(pad_forces)
        total = r_reach + r_lift + self.lambda_c * r_contact - penalty
        parts = {
            "reach": r_reach,
            "lift": r_lift,
            "contact": r_contact,
            "force_penalty": penalty,
        }
        return total, parts


if __name__ == "__main__":
    car = ContactAwareReward()
    car.reset()
    normals = [(0.0, 1.0, 0.0), (0.0, -1.0, 0.0)]
    surf = (0.0, 1.0, 0.0)
    for step in range(12):
        reward, parts = car(dist=0.02, object_height=0.12,
                            pad_forces=[3.0, 4.5], pad_normals=normals,
                            surface_normal=surf)
        print(step, round(reward, 4), {k: round(v, 4) for k, v in parts.items()})
