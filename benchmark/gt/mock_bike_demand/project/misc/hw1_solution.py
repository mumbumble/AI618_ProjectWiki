"""Homework 1 solution: sorting algorithms and simple string helpers."""


def bubble_sort(items):
    """Return a new list sorted with bubble sort."""
    data = list(items)
    n = len(data)
    for i in range(n - 1):
        swapped = False
        for j in range(n - 1 - i):
            if data[j] > data[j + 1]:
                data[j], data[j + 1] = data[j + 1], data[j]
                swapped = True
        # If no swaps happened in a full pass, the list is already sorted.
        if not swapped:
            break
    return data


def merge(left, right):
    """Merge two already-sorted lists into one sorted list."""
    merged = []
    i = 0
    j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged


def merge_sort(items):
    """Return a new list sorted with merge sort."""
    if len(items) <= 1:
        return list(items)
    mid = len(items) // 2
    return merge(merge_sort(items[:mid]), merge_sort(items[mid:]))


def is_palindrome(s):
    """Check whether a string reads the same forwards and backwards.

    Case and non-alphanumeric characters are ignored.
    """
    cleaned = [ch.lower() for ch in s if ch.isalnum()]
    return cleaned == cleaned[::-1]


def count_vowels(s):
    """Count the vowels (a, e, i, o, u) in a string, ignoring case."""
    vowels = "aeiou"
    return sum(1 for ch in s.lower() if ch in vowels)


def main():
    numbers = [29, 3, 17, 8, 42, 1, 15]
    print("Original:   ", numbers)
    print("Bubble sort:", bubble_sort(numbers))
    print("Merge sort: ", merge_sort(numbers))

    samples = ["Racecar", "Hello", "A man, a plan, a canal: Panama"]
    for word in samples:
        print(
            f"{word!r}: palindrome={is_palindrome(word)}, "
            f"vowels={count_vowels(word)}"
        )


if __name__ == "__main__":
    main()
