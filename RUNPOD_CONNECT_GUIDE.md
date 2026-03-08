# RunPod vLLM 터널 연결 가이드

## 사전 조건
- EC2 인스턴스가 실행 중이어야 함
- RunPod Pod(vLLM)이 실행 중이어야 함
- EC2에 RunPod SSH 키(`~/.ssh/runpod_key`)가 존재해야 함

## 1. RunPod TCP 주소 확인

RunPod 대시보드 → Pods → vLLM → Connect 탭 → **SSH over exposed TCP** 항목에서 확인

```
ssh root@{IP} -p {PORT} -i ~/.ssh/id_ed25519
```

> **IP와 PORT는 Pod 재시작마다 변경되므로 매번 확인 필요**

## 2. EC2 접속

```bash
ssh -i ARAE_key.pem ubuntu@43.200.42.14
```

## 3. SSH 터널 설정

EC2 내부에서 실행:

```bash
ssh -i ~/.ssh/runpod_key -o StrictHostKeyChecking=no -L 8888:localhost:8000 -N -f root@{RUNPOD_TCP_IP} -p {RUNPOD_TCP_PORT}
```

| 옵션 | 설명 |
|------|------|
| `-L 8888:localhost:8000` | EC2의 8888 포트 → RunPod의 vLLM 8000 포트로 포워딩 |
| `-N` | 원격 명령 실행 없이 터널만 유지 |
| `-f` | 백그라운드 실행 |

### 예시 (2026-03-08 기준)

```bash
ssh -i ~/.ssh/runpod_key -o StrictHostKeyChecking=no -L 8888:localhost:8000 -N -f root@154.54.102.50 -p 17342
```

## 4. 연결 확인

```bash
# 포트 리스닝 확인
ss -tlnp | grep 8888

# vLLM 모델 목록 확인
curl -s http://localhost:8888/v1/models | python3 -m json.tool
```

정상 응답 시 아래 모델 3개가 표시됨:
- `Qwen/Qwen3-8B` — 베이스 모델
- `cv_agent` — CV 분석 LoRA
- `search_agent` — 검색 LoRA

## 5. 터널 종료 (필요 시)

```bash
# 터널 프로세스 확인
ps aux | grep "ssh.*runpod" | grep -v grep

# 프로세스 종료
kill {PID}
```

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `Connection refused` | RunPod Pod이 꺼져 있음 | RunPod 대시보드에서 Pod 시작 |
| `Connection timed out` | TCP 주소 변경됨 | 대시보드에서 새 IP/PORT 확인 후 재연결 |
| 포트 8888 이미 사용 중 | 이전 터널이 남아있음 | `kill` 후 재연결 |
| vLLM 응답 없음 (포트는 열림) | vLLM 서버 아직 로딩 중 | RunPod Logs 탭에서 상태 확인, 잠시 대기 |
