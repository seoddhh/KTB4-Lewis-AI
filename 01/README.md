# 중복 파일 탐색기 프로그램

`duplicate_finder.py`는 사용자가 지정한 폴더 안에서 내용이 같은 중복 파일을 찾아주는 Python 프로그램입니다.

파일 이름이 달라도 실제 파일 내용이 같으면 중복 파일로 판단합니다. 예를 들어 `report.pdf`, `report (1).pdf`, `과제제출용.pdf`처럼 이름이 달라도 내부 내용이 같으면 같은 중복 그룹으로 출력됩니다.

반대로 `최종.docx`, `최종_최종.docx`, `진짜최종.docx`처럼 이름이 비슷해도 내부 내용이 조금이라도 다르면 중복 파일로 판단하지 않습니다. 이 프로그램은 파일 이름의 유사성이 아니라 해시값을 바탕으로 파일 내용의 일치 여부를 검사합니다.


## 주요 기능

- 검사할 폴더 경로 입력
- 하위 폴더 포함 여부 선택
- 파일 크기 기준으로 1차 중복 후보 필터링
- SHA-256 해시값으로 실제 파일 내용 비교
- 중복 파일 그룹 목록 출력
- 사용자가 선택한 중복 파일 삭제
- 삭제 전 재확인 절차 제공

## 사용 기술

이 프로그램은 Python 기본 내장 라이브러리만 사용합니다.

사용한 주요 라이브러리는 다음과 같습니다.

```python
import argparse
import asyncio
import hashlib
from collections import defaultdict
from pathlib import Path
```

따라서 별도의 가상환경 설정이 필요하지 않습니다.

단, `asyncio.to_thread()`를 사용하므로 Python 3.9 이상 사용을 권장합니다.

## 실행 방법

`duplicate_finder.py`가 있는 폴더에서 다음 명령어를 실행합니다.

```bash
python3 duplicate_finder.py
```

또는 검사할 폴더의 경로를 명령어에 바로 지정할 수 있습니다.

```bash
python3 duplicate_finder.py ~/Downloads
```

하위 폴더까지 포함해서 검사하려면 `-r` 옵션을 사용합니다.

```bash
python3 duplicate_finder.py ~/Downloads -r
```

동시에 해시를 계산할 파일 수를 조절하려면 `-c` 옵션을 사용합니다.

```bash
python3 duplicate_finder.py ~/Downloads -r -c 4
```

`-c`의 기본값은 4입니다.

## 실행 예시

```text
검사할 폴더 경로를 입력하세요: ~/Downloads
하위 폴더까지 검사할까요? (y/n): y
검사 폴더: /Users/user/Downloads
하위 폴더 포함: 예
전체 파일 수: 128개
중복 가능성이 있는 파일: 12개
해시 계산 대상 파일: 12개
검사 진행률: 12/12

중복 파일 그룹 2개 발견

[그룹 1]
크기: 2.45 MB
해시: a8f32...
파일 목록:
  1. /Users/user/Downloads/report.pdf
  2. /Users/user/Downloads/report (1).pdf

명령어: list, delete, exit
>
```

## 검사 방식

이 프로그램은 바로 모든 파일의 내용을 비교하지 않습니다. 효율을 위해 다음 순서로 검사합니다.

1. 폴더 안의 파일 목록을 수집합니다.
2. 파일 크기가 같은 파일끼리 먼저 묶습니다.
3. 크기가 같은 파일만 SHA-256 해시값을 계산합니다.
4. 해시값이 같은 파일들을 중복 파일 그룹으로 출력합니다.

파일 크기가 다르면 내용이 같을 수 없으므로 해시 계산 대상에서 제외합니다. 이 방식으로 불필요한 파일 읽기를 줄일 수 있습니다.

SHA-256 해시값은 파일 내용을 기준으로 만들어지는 긴 문자열입니다. 파일 내용이 완전히 같으면 같은 해시값이 나오고, 내용이 조금이라도 다르면 일반적으로 다른 해시값이 나옵니다. 따라서 이름이 비슷한 파일이라도 내용이 다르면 중복으로 표시되지 않습니다.

## 명령어

검사가 끝난 뒤에는 다음 명령어를 사용할 수 있습니다.

### `list`

중복 파일 목록을 다시 출력합니다.

```text
> list
```

### `delete`

중복 파일 중 삭제할 파일 번호를 선택합니다.

```text
> delete
삭제할 파일 번호를 입력하세요. 여러 개는 쉼표로 구분합니다. 취소는 빈 값 입력: 2,3
```

삭제 전에는 선택한 파일 목록을 다시 보여주고, `yes`를 입력해야 실제로 삭제됩니다.

```text
정말 삭제할까요? 이 작업은 되돌릴 수 없습니다. (yes/no): yes
```

삭제는 터미널의 `rm` 명령어가 아니라 Python의 `Path.unlink()`로 처리됩니다.

### `exit`

프로그램을 종료합니다.

```text
> exit
```

## 비동기 처리 설명

이 프로그램에서 비동기 처리는 파일 해시 계산 부분에 적용되어 있습니다.

중복 파일 탐지는 파일 내용을 직접 읽어서 해시값을 계산해야 하므로 파일 수가 많거나 용량이 크면 시간이 걸릴 수 있습니다. 그래서 각 파일의 해시 계산 작업을 비동기 태스크로 만들고, 동시에 여러 파일을 검사하도록 구현했습니다.

핵심 코드 구조는 다음과 같습니다.

```python
async def hash_file(path, semaphore):
    async with semaphore:
        file_hash = await asyncio.to_thread(calculate_file_hash, path)
        return path, file_hash
```

여러 파일은 `asyncio.create_task()`로 작업을 만들고, `asyncio.as_completed()`로 완료된 작업부터 처리합니다.

```python
tasks = [
    asyncio.create_task(hash_file(path, semaphore))
    for path in duplicate_candidates
]

for task in asyncio.as_completed(tasks):
    result = await task
```

또한 `asyncio.Semaphore`를 사용해 동시에 처리하는 파일 수를 제한합니다. 이 제한이 없으면 너무 많은 파일을 한 번에 읽으려고 해서 컴퓨터에 부담이 될 수 있습니다.

## 주의사항

- `delete` 명령어로 삭제한 파일은 휴지통으로 이동하지 않고 바로 삭제됩니다.
- 삭제 전 반드시 파일 경로를 확인해야 합니다.
- 중요한 폴더를 검사할 때는 먼저 `list`로 삭제할 파일 번호와 경로를 충분히 확인하는 것을 권장합니다.
- 시스템 폴더나 권한이 제한된 폴더는 일부 파일을 읽지 못할 수 있습니다.
- .venv, node_modules, .git 같은 개발 환경 폴더는 중복 파일이 많이 발견될 수 있지만, 삭제하면 환경이 깨질 수 있으므로 삭제 대상에서 제외하는 것을 권장합니다.

## 도움말

사용 가능한 옵션은 다음 명령어로 확인할 수 있습니다.

```bash
python3 duplicate_finder.py --help

```

## 회고

1.우선 CLI 환경에서 git처럼 명령어 뒤에 옵션을 붙여 실행하려면 argparse 라이브러리가 필요하다는 것을 알게 되었다. 이때 명령어에 붙이는 옵션들을 인자(argument)라고 한다.

2.비동기(async/await)를 언제, 왜 써야 하는지 알게 되었다. 병목 현상이 생기는 작업을 처리할 때 멈춰서 기다리지 않고 그 시간에 다른 작업을 실행해 효율을 높이는 것으로 이 코드에선 파일을 읽고 해시값을 찾는 절차처럼 대기 시간이 발생하는 지점에서 사용하는것을 알게 되었다.

3.중복 파일을 찾을 때 이름이 달라도 '파일 크기와 해시값'이 같으면 완전히 똑같은 파일이라는 사실을 알게 되었다.

