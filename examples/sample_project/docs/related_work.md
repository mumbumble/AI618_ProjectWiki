# 관련 연구 메모

## 음성 기반 얼굴 애니메이션
- FaceFormer: transformer 기반 autoregressive 3D 얼굴 애니메이션. LVE 지표를 사용.
- CodeTalker: 이산 코드북으로 표정 공간을 양자화.

## 감정 표현
- EMOTE: 감정 레이블과 강도를 조건으로 표정을 생성하고 lip-reading loss로 입 모양을 맞춤.
- 우리 방법과 차이: 우리는 diffusion 기반이고 감정 일관성 loss를 추가함.

## Diffusion
- DDPM 기반 motion diffusion 계열(MDM 등)이 동작 생성에서 다양성을 보여줌.
