# Change Log

## 2026-09-24 - Portable Codex Relay and public GitHub preparation

- Added Telegram-only, Discord-only, and combined startup; Discord can now pair securely by DM without a preconfigured numeric user ID.
- Added OS-neutral state paths, Codex discovery through `PATH`, Windows/macOS execution without Linux `setpriv`, and safe `.env` loading.
- Added an interactive setup wizard, Python package metadata, MIT license, portable configuration docs, and Linux/macOS/Windows CI.
- Kept systemd, persistent root, Android build, and artifact publishing as optional Raspberry Pi extensions.
- Expanded security coverage and portability tests; the complete suite now contains 99 tests.

## 2026-09-24 - Discord 지속 root 대화 컨텍스트 유지

- 원인: Discord 상태와 세션 슬롯은 저장됐지만 `root-always` 실행이 매번 `--ephemeral` 새 대화로 강제되어 후속 메시지의 Codex 컨텍스트가 끊겼다.
- 변경: 일반 권한과 지속 root의 Codex 세션 ID를 슬롯별로 분리 저장하고, `root-always`는 root 전용 Codex 저장소에서 `exec resume`으로 이어가도록 변경했다. 1회성 root는 계속 ephemeral이다.
- 세션 관리: 대화 초기화·이름 변경·삭제는 일반 및 root 연결을 함께 처리하며, 현재 권한에 맞는 대화 존재 여부를 표시한다.
- 보안: root 저장소는 계속 root 전용 0700이고 릴레이 비밀 환경은 root 자식에 전달하지 않는다.

## 2026-09-24 - Discord 중심 안정화와 운영 복구

- 요청: 외부 체류 전 현재 봇을 Git으로 백업하고 Discord 중심 운용에서 오류가 날 수 있는 부분을 찾아 수정·배포.
- 복구: 운영 런타임에만 남고 로컬 Git/Pi 소스에는 일부만 남아 있던 진행 표시, 일반 파일 첨부, 지속 root, 안전한 45초 지연 재시작 코드를 보존·병합했다.
- 수정: Discord Gateway 준비/사망 감지, Telegram 시작 장애 격리, full/root 1회 권한 원자 소비, 모든 root 작업의 ephemeral 분리, 이미지+파일 혼합 첨부, 종료·취소 경쟁, 검증 스크립트 import 경로를 고쳤다.
- Git: 기준 백업 `96b5502`, 안정성 수정 `9ddee2a`, 복구·통합 `130a4ae`, 프로젝트 검증 수정 `084a8f2`.
- 검증: Windows와 Pi에서 문법 검사 및 단위 테스트 80개 통과. 실제 Telegram 인증과 Codex turn, Discord 패널 10개·설정 9개·위험 확인 3종·콜백·모달·세션 관리도 통과.
- 운영: 백업 `/srv/deploy-backups/telegram-codex-bot/20260923T151829Z`; 지연 재시작 후 서비스 active/running, 새 PID 3261996, NRestarts=0, error 로그 0건.
- 무결성: 로컬·Pi 소스·운영 런타임의 `app.py`, `codex_progress.py`, Discord 모듈, 공통 오류·requirements 해시 일치.
- 현재 권한: Telegram과 Discord 모두 기존 사용자 선택인 `root-always` 유지. 모든 root 작업은 저장 세션과 분리된 ephemeral 실행.
- 남은 외부 상태: `simple-silent-camera`가 root:root 0700이라 프로젝트 목록에서 건너뛰며 경고 1건을 남긴다. 다른 프로젝트 권한은 이번 범위에서 변경하지 않았다.
- 롤백: 위 백업의 runtime과 systemd/sudoers 파일을 복원하고 daemon-reload 후 해당 서비스만 재시작.

## 2026-08-16 - 지속 root 권한

- 요청: 매 작업마다 root 1회 권한을 다시 선택하지 않고 계속 root로 실행할 수 있는 선택지 추가.
- 변경: Telegram과 Discord 권한 메뉴에 별도 확인을 거치는 `root 계속`을 추가했다. 선택 상태는 플랫폼별로 분리되며 `safe`·`read`·`auto`로 변경할 때까지 서비스 재시작 후에도 유지된다.
- 보안: 봇 서비스는 기존처럼 일반 사용자로 실행한다. 각 root 작업만 전용 sudo 실행기, 임시 Codex 인증 디렉터리, 비밀 환경 제거, `--ephemeral` 저장 세션 분리를 그대로 적용한다.
- 변경 파일: `app.py`, `discord_controls.py`, `tests/test_app.py`, `tests/test_controls.py`, `deploy/verify_discord_controls.py`, `deploy/telegram-codex-bot.service`, `deploy/telegram-codex-bot.sudoers`, `README.md`, `docs/change-log.md`.
- 검증: 문법 검사와 단위 테스트 69개 통과. 운영 배포 및 연결 검증은 아래 운영 적용 기록에 추가한다.

## 2026-08-15 - 작업 맥락 분리와 리모컨 마찰 완화

- 요청: 사용자 관점에서 불편한 흐름을 모두 줄이기.
- 변경: Telegram·Discord의 프로젝트, 세션, 모델, 추론 강도, 권한 상태와 실행 키를 분리했다. 실행 중에도 다음 작업의 프로젝트·AI 설정을 준비할 수 있으며 실행 시작 시점의 설정은 작업에 고정된다.
- 변경: `full`을 명시적 확인이 필요한 1회성 권한으로 바꾸고, `root`와 같이 작업 시작 즉시 `safe`로 복귀하게 했다.
- 변경: Telegram 세션 메뉴에 생성·이름 변경·삭제 흐름과 초기화 확인을 추가하고, 현재/전체 작업 중지를 노출했다. 사진을 먼저 보내고 다음 메시지로 작업을 지시하는 흐름도 추가했다.
- 변경: 상태 문구를 실제 외부 연결 건강 상태처럼 보이지 않게 수정하고, 세션 이름에 한글을 허용했다. Discord 패널에 전체 작업 중지를 추가했다.
- 변경: 기존 상태를 불러올 때 남아 있던 위험 권한·임시 입력을 폐기하고, Discord 컨트롤은 허용 사용자 interaction만 처리하게 했다. Telegram의 삭제·초기화 확인도 표시한 대상 세션에 고정했다.
- 변경 파일: `app.py`, `discord_controls.py`, `deploy/verify_discord_controls.py`, `tests/test_app.py`, `tests/test_controls.py`, `tests/test_discord_bridge.py`, `tests/test_images.py`, `tests/test_sessions.py`, `README.md`, `docs/change-log.md`.
- 검증: `python -m compileall app.py discord_controls.py tests` 및 `python -m unittest discover -s tests -v` 통과 (57개).
- 배포 상태: 로컬 변경만 완료, 운영 미배포.
- 롤백: 이 변경 파일을 이전 검증본으로 복원하고 배포하지 않은 상태를 유지.

### 운영 적용 및 검증

- 배포: 2026-08-16 KST Pi 운영 반영. `telegram-codex-bot.service`만 재시작했으며 Caddy와 다른 서비스는 변경하지 않음.
- 백업: `/srv/deploy-backups/telegram-codex-bot/20260815T150138Z-pre-ux-context-controls`, `/srv/deploy-backups/telegram-codex-bot/20260815T150140Z`.
- 검증: Pi 문법 검사와 단위 테스트 62개 통과, Discord 컨트롤 구조·콜백 검증 통과, Telegram `/menu` 등록 및 실제 메뉴 전송 통과, source/runtime 해시 일치, 서비스 enabled·active, `NRestarts=0`, 두 플랫폼 권한 `safe` 확인.
- 롤백: 위 백업의 `runtime`을 `/srv/telegram-codex-bot`에 복원한 뒤 `telegram-codex-bot.service`를 재시작하고 동일 검증을 반복.

## 2026-08-14 - Telegram·Discord 빠른 조작 UX

- 요청: Telegram과 Discord 모두 반복 명령 입력 없이 더 편하게 조작하도록 개선.
- 변경: Telegram `/menu` 인라인 리모컨과 인증된 callback 처리, 프로젝트·세션·모델·추론 강도·권한·상태·초기화·취소 버튼을 추가함. `full`·`root`는 별도 확인 화면을 유지함.
- 변경: Discord 영구 패널에 상태 보기와 도움말 버튼을 추가하고 결과는 개인에게만 보이는 응답으로 표시함.
- 변경 파일: `app.py`, `discord_bridge.py`, `discord_controls.py`, `tests/test_app.py`, `deploy/verify_discord_controls.py`, `deploy/verify_telegram_menu.py`, `README.md`, `docs/change-log.md`.
- 검증: 로컬·Pi 문법 검사와 단위 테스트 54개 통과. Telegram `/menu` 등록·실전송, 실제 Codex smoke, Discord 패널 11개 구성요소·설정 8개·위험 확인 2종·콜백·모달 검증 통과.
- 배포 상태: 운영 반영 완료. 서비스 `enabled`·`active`, `NRestarts=0`, Telegram·Discord 연결 정상, 소스·런타임 해시 일치.
- 백업: `/srv/deploy-backups/telegram-codex-bot/20260814T042652Z-pre-dual-ux`, `/srv/deploy-backups/telegram-codex-bot/20260814T042731Z`.
- 롤백: 배포 백업의 위 파일을 복원하고 `telegram-codex-bot.service`를 재시작.

## 2026-08-14 - Discord typing API 호환성 수정

- 요청: 반복적으로 발생하는 봇 오류 진단 및 해결.
- 원인: 운영 `discord.py 2.7.1`에서 제거된 `trigger_typing()` 호출로 Discord 작업 중 5초마다 typing 전송이 실패함.
- 변경: 지원되는 `typing()` awaitable을 사용하도록 수정하고 회귀 테스트를 추가함.
- 변경 파일: `discord_bridge.py`, `tests/test_discord_bridge.py`, `docs/change-log.md`.
- 검증: 로컬·Pi 문법 검사와 단위 테스트 50개 통과, Telegram API 및 실제 Codex smoke 통과, Discord typing API HTTP 204 확인.
- 배포 상태: 운영 반영 완료. 서비스 `enabled`·`active`, `NRestarts=0`, Discord Gateway와 컨트롤 패널 연결 정상, 소스·런타임 해시 일치.
- 백업: `/srv/deploy-backups/telegram-codex-bot/20260814T041836Z-pre-typing-fix`, `/srv/deploy-backups/telegram-codex-bot/20260814T041837Z`.
- 롤백: 배포 백업의 위 파일을 복원하고 `telegram-codex-bot.service`를 재시작.

## 2026-08-13 - Discord Gateway bridge

- 요청: 기존 Telegram Codex 봇을 Discord DM 또는 지정 채널에서도 사용하도록 연결.
- 변경: Discord Gateway 어댑터, 단일 사용자·선택 채널 제한, `!` 명령 변환, 이미지 전달, 보안 설정 도우미, 가상환경 의존성 설치와 서비스 실행 경로 추가.
- 변경 파일: `app.py`, `discord_bridge.py`, `relay_errors.py`, `requirements.txt`, `README.md`, `deploy/*`, `tests/*`.
- 검증: 로컬 문법 검사와 단위 테스트 후 Pi 대상 검증 예정.
- 배포 상태: 미배포.
- 남은 문제: 실제 Discord 토큰과 허용 사용자 ID가 운영 환경에 있어야 Gateway 연결을 검증할 수 있음.
- 롤백: 배포 전 백업의 런타임·unit 파일을 복원하고 `daemon-reload` 후 서비스 재시작.

### 운영 적용

- Pi 백업: `/srv/deploy-backups/telegram-codex-bot/20260813T101502Z-pre-discord`, `/srv/deploy-backups/telegram-codex-bot/20260813T101616Z`.
- 검증: 로컬 및 Pi 단위 테스트 40개 통과, systemd unit 검사, Telegram self-test, 실제 Codex smoke, source/runtime hash 일치, 서비스 active 및 `NRestarts=0`.
- 보안: 운영 상태의 잔존 `full` 권한을 백업 후 `safe`로 복귀. Discord 토큰과 ID는 보호된 환경 파일에만 저장.
- 후속 수정: DM 전용 연결은 privileged Message Content Intent를 요청하지 않고, 지정 서버 채널 연결에서만 요청하도록 변경.

### 최종 상태 정정

- 배포 상태: Pi 운영 배포 및 Discord DM Gateway 연결 완료.
- 추가 백업: `/srv/deploy-backups/telegram-codex-bot/20260813T102137Z`.
- 최종 검증: 로컬 및 Pi 단위 테스트 42개 통과, Discord API 토큰 인증 성공, Gateway 및 어댑터 연결 로그 확인, 서비스 `active`, `NRestarts=0`, 실행 파일 hash 일치.
- 남은 수동 증거: 허용된 Discord 사용자 계정에서 `!status` 송수신 확인.

## 2026-08-13 - Discord button control panel

- 요청: 반복해서 명령을 입력하지 않고 Discord 버튼·선택 메뉴로 프로젝트, 세션, AI 설정과 권한을 편하게 조작.
- 변경: 시작 시 DM 컨트롤 패널 전송, 프로젝트·세션 선택, 새 세션 모달, 초기화 확인, 작업 취소, 모델·추론 선택, 권한 버튼과 `full`·`root` 이중 확인 추가.
- 변경 파일: `app.py`, `discord_bridge.py`, `discord_controls.py`, `deploy/install.sh`, `deploy/verify_discord_controls.py`, `README.md`, `tests/test_discord_bridge.py`.
- 보안: 기존 단일 사용자·DM 제한을 유지하고, 위험 권한은 확인 화면 뒤에서만 적용하며 결과 피드백은 ephemeral 응답으로 제한.
- 검증·배포 상태: 로컬 및 Pi 검증 후 기록 예정.
- 롤백: 운영 백업의 `discord_bridge.py`, `discord_controls.py`, `app.py`, unit을 복원하고 서비스 재시작.

### 운영 적용 및 검증

- 백업: `/srv/deploy-backups/telegram-codex-bot/20260813T102930Z-pre-controls`, `/srv/deploy-backups/telegram-codex-bot/20260813T103036Z`.
- 테스트: 로컬 및 Pi 단위 테스트 44개 통과, Telegram self-test 및 실제 Codex smoke 통과.
- Discord UI: 실제 DM에서 메인 패널 3행·7개 컴포넌트 확인. 실제 `discord.py`로 설정 패널 8개 컴포넌트, 위험 권한 확인 2종, 새로고침·권한·새 세션 모달 콜백을 임시 상태에서 검증.
- 운영 상태: `telegram-codex-bot.service` active, `NRestarts=0`, Gateway 및 패널 전송 성공, error 이상 journal 없음, source/runtime hash 일치, persisted permission `safe`.
- 롤백 수행: 없음. 검증 실패는 배포 코드가 아닌 검증 스크립트의 기본 행 처리였으며 수정 후 재검증 통과.
- 최종 UX 조정: 메인·설정 패널은 서비스 프로세스 수명 동안 만료되지 않게 하고, 재시작 시 새 패널을 자동 전송. 위험 확인창과 새 세션 모달만 5분 제한 유지.
- 최종 UX 배포 백업: `/srv/deploy-backups/telegram-codex-bot/20260813T103705Z`.

## 2026-08-13 - Discord session rename and delete

- 요청: Discord 패널에서 세션 이름 변경과 삭제까지 처리.
- 변경: 이름 변경 모달, 삭제 확인 화면, Codex session ID 보존 rename, 실행 중 세션 보호, 마지막 세션 삭제 시 빈 `main` 자동 생성.
- 변경 파일: `app.py`, `discord_controls.py`, `tests/test_sessions.py`, `deploy/verify_discord_controls.py`, `README.md`.
- 검증·배포 상태: 로컬 및 Pi 검증 후 기록 예정.
- 롤백: 배포 백업의 런타임 파일과 상태 파일을 복원하고 서비스 재시작.

### 운영 적용 및 검증

- 백업: `/srv/deploy-backups/telegram-codex-bot/20260813T104832Z-pre-session-management`, `/srv/deploy-backups/telegram-codex-bot/20260813T104925Z`.
- 테스트: 로컬 및 Pi 단위 테스트 48개와 문법 검사 통과. Discord 메인 패널 9개·설정 패널 8개 컴포넌트, 이름 변경 모달의 session ID 보존, 삭제 확인 콜백과 마지막 세션의 `main` 복구를 임시 상태에서 검증.
- 실제 연결: Telegram API 및 실제 Codex smoke 통과. Discord Gateway 연결과 새 컨트롤 패널 전송 성공.
- 운영 상태: `telegram-codex-bot.service` enabled·active, `NRestarts=0`, systemd unit 검사 통과, error 이상 journal 없음, 변경된 source/runtime hash 일치, 상태 파일 `user:user 0600`, 환경 파일 `root:root 0600`.
- 참고: 음성 기능용 선택 패키지 PyNaCl·davey 미설치 경고만 있으며 현재 텍스트·버튼 기능에는 영향 없음.
- 롤백 수행: 없음.

## 2026-08-16 - Platform-separated controls and safer remote workflow

- 요청: 사용자 기준 불편 요소를 개선하고 Pi 운영에 반영.
- 변경: Telegram/Discord 상태와 실행 키 분리, Discord 패널 사용자 권한 확인, `full` 1회 확인, 세션 삭제·초기화 대상 고정, 이미지 입력 취소·다음 메시지 작업 전환, 실행 취소 범위와 세션 관리 흐름 개선.
- 변경 파일: `app.py`, `discord_controls.py`, `README.md`, `tests/test_app.py`, `tests/test_controls.py`, `tests/test_discord_bridge.py`, `tests/test_images.py`, `tests/test_sessions.py`, `deploy/verify_discord_controls.py`.
- 백업: `/srv/deploy-backups/telegram-codex-bot/20260815T150138Z-pre-ux-context-controls`, `/srv/deploy-backups/telegram-codex-bot/20260815T150140Z`.
- 검증: Pi 문법 검사와 단위 테스트 62개 통과, Discord 컨트롤 구조·콜백 검증 통과, Telegram `/menu` 등록 및 실제 메뉴 전송 통과, source/runtime 해시 일치, 서비스 enabled·active, `NRestarts=0`, 두 플랫폼 권한 `safe` 확인.
- 한계: Discord Gateway 연결은 확인했으나, 재시작 직후 자동 DM 패널 전송은 Discord 403(봇과 허용 사용자의 공통 서버 없음)으로 차단됐다. 패널 구조·콜백 검증은 통과했으며, 공통 서버 또는 Discord DM 수신 조건을 갖춘 뒤 `!panel`로 다시 열 수 있다.
- 롤백: `/srv/deploy-backups/telegram-codex-bot/20260815T150140Z/runtime`을 `/srv/telegram-codex-bot`에 복원하고 `telegram-codex-bot.service`를 재시작.

## 2026-08-13 - Explicit zeta-chat-ui project registration

- 요청: Discord 프로젝트 선택 목록에 `zeta-chat-ui` 추가.
- 원인: Pi 폴더는 존재하지만 루트 `.git`이 없어 Git 프로젝트 전용 목록에서 제외됨.
- 변경: `CODEX_EXTRA_PROJECTS`에 지정된 바로 아래 폴더만 명시적 예외로 등록. 다른 일반 폴더와 경로 이탈 차단은 유지.
- 변경 파일: `app.py`, `tests/test_app.py`, `deploy/telegram-codex-bot.env.example`, `deploy/verify_project_catalog.py`, `README.md`.
- 검증·배포 상태: 로컬 및 Pi 검증 후 기록 예정.
- 롤백: 운영 백업의 런타임·환경 설정을 복원하고 서비스 재시작.

### 운영 적용 및 검증

- 백업: `/srv/deploy-backups/telegram-codex-bot/20260813T111739Z-pre-zeta-registration`, `/srv/deploy-backups/telegram-codex-bot/20260813T111752Z`.
- 설정: `/etc/telegram-codex-bot.env`의 기존 값을 보존하면서 `CODEX_EXTRA_PROJECTS`에 `zeta-chat-ui` 추가.
- 테스트: 로컬 및 Pi 단위 테스트 49개와 문법 검사 통과.
- 실제 목록: 5개 프로젝트 중 `zeta-chat-ui`가 표시되고 `/home/user/Raspberry_Pi/zeta-chat-ui`로 안전하게 resolve됨. 등록하지 않은 일반 폴더는 계속 제외됨.
- 운영 상태: 서비스 active, `NRestarts=0`, Discord Gateway 연결 및 새 패널 전송 성공, source/runtime hash 일치, 환경·상태 파일 권한 유지.
- 롤백 수행: 없음.
## 2026-08-16 - Telegram·Discord 공통 Codex 진행 표시

- 요청: 두 플랫폼의 유용한 기능을 공통 로직으로 통합하고, Codex의 공개 추론 요약과 작업 진행을 새 메시지 없이 하나의 메시지에 누적 표시.
- 변경: JSONL 스트리밍 처리와 공통 진행 상태 모듈을 추가하고, Telegram `editMessageText`와 Discord `Message.edit` 어댑터를 연결했다. 상태 계산도 공통 스냅샷으로 통합했다.
- 메시지 수명: 모델·인텔리전스·권한·취소 안내를 담던 시작 메시지는 제거했다. 최초 진행 메시지는 완료·실패·중지 상태와 총 소요 시간으로 수정해 유지하며 최종 답변도 별도로 유지한다.
- 보안: 공개 summary/text와 일반화한 작업 종류만 표시하고 raw/encrypted reasoning, 원시 명령 출력, stderr는 진행 메시지에서 제외한다.
- 변경 파일: `app.py`, `codex_progress.py`, `discord_bridge.py`, `discord_controls.py`, `deploy/install.sh`, `deploy/telegram-codex-deploy`, `tests/test_app.py`, `tests/test_discord_bridge.py`, `tests/test_progress.py`, `README.md`, `docs/change-log.md`.
- 검증: 문법 검사, 셸 문법 검사, Telegram·Discord 어댑터 및 공통 진행 수명주기를 포함한 단위 테스트 78개 통과. 운영 API 실송신과 배포·서비스 재시작은 미수행.
- 배포 상태: 로컬 변경만 완료, 운영 미배포.
## 2026-09-24 - 외부 앱 테스트 빌드·산출물 전달 준비
- 목표: Discord 중심 원격 Codex에서 APK 빌드, Telegram 공통 UX, 외부 파일 다운로드, 사용량 표시와 후속 지시 예약을 제공.
- 커밋: 로컬 `ecfa0ad`·`01f3963`, Pi `c4cc025`·`4e61893`; 기존 Pi dirty 파일 3개는 보존.
- 변경: 검증된 artifact outbox, Drive 원자 게시·백업·공개 SHA-256 확인, 공통 다운로드 카드, `/usage`, `/steer` FIFO 대기열 추가.
- 스킬: `pi-android-apk-build`, `pi-drive-artifact-release`, `pi-remote-codex-ops`를 만들고 `/home/user/.codex/skills`에 설치.
- 검증: Windows/Pi Python·shell 검사와 단위 테스트 90개 통과; Telegram 명령 등록·인증·실제 Codex turn, Discord Gateway·패널 연결 확인.
- 게시 증거: readiness TXT 64 bytes, SHA-256 `d31d6e8bfe0ca932719f35006aeab6e09f279c773d1a673c111ce6449fb10c74`, 공개 재다운로드 일치.
- 배포: 백업 `/srv/deploy-backups/telegram-codex-bot/20260923T164531Z`, 서비스 PID 3315831, active/running, NRestarts=0.
- APK 상태: JDK 17·SDK·Gradle 캐시·직렬 빌드 실행기는 배포됐지만 QEMU AAPT2 link는 실패; 실행기는 native ARM64 AAPT2 미설치 시 fail-fast.
- 롤백: 실패한 Docker 이미지·AAPT 캐시·Debian 패키지 9개를 제거. 운영 롤백은 위 백업의 runtime·helpers·sudoers 복원 후 daemon-reload/restart.
- 남은 문제: 검증된 third-party ARM64 AAPT2 설치는 사용자 명시 승인 필요. `apk.dcout.cloud` 공개 DNS A 레코드도 없음.
