#!/usr/bin/env python3
import argparse
import asyncio
import hashlib
import os
from collections import defaultdict
from pathlib import Path


CHUNK_SIZE = 1024 * 1024


def format_size(size):
    """파일 크기를 사람이 읽기 쉬운 단위로 변환합니다."""
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024


def normalize_path(path_text):
    """사용자가 입력한 경로에서 ~ 같은 표현을 실제 경로로 변환합니다."""
    return Path(path_text).expanduser().resolve()


def collect_files(folder, recursive):
    """검사할 파일 목록을 수집합니다."""
    if recursive:
        candidates = folder.rglob("*")
    else:
        candidates = folder.iterdir()

    files = []
    for path in candidates:
        try:
            if path.is_file():
                files.append(path)
        except OSError:
            continue

    return files


def group_files_by_size(files):
    """크기가 같은 파일끼리 먼저 묶습니다."""
    grouped = defaultdict(list)

    for path in files:
        try:
            grouped[path.stat().st_size].append(path)
        except OSError:
            continue

    return {size: paths for size, paths in grouped.items() if len(paths) > 1}


def calculate_file_hash(path):
    """파일 내용을 읽어서 SHA-256 해시값을 계산합니다."""
    hasher = hashlib.sha256()

    with open(path, "rb") as file:
        while True:
            chunk = file.read(CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)

    return hasher.hexdigest()


async def hash_file(path, semaphore):
    """파일 해시 계산을 별도 스레드에서 실행합니다."""
    async with semaphore:
        try:
            file_hash = await asyncio.to_thread(calculate_file_hash, path)
            size = await asyncio.to_thread(lambda: path.stat().st_size)
            return path, size, file_hash, None
        except OSError as error:
            return path, 0, "", error


async def find_duplicate_groups(files_by_size, max_concurrent):
    """크기가 같은 파일들의 해시를 비동기로 계산해 중복 그룹을 찾습니다."""
    semaphore = asyncio.Semaphore(max_concurrent)
    duplicate_candidates = [
        path
        for paths in files_by_size.values()
        for path in paths
    ]

    if not duplicate_candidates:
        return []

    print(f"해시 계산 대상 파일: {len(duplicate_candidates)}개")

    tasks = [
        asyncio.create_task(hash_file(path, semaphore))
        for path in duplicate_candidates
    ]

    hashed_files = []
    completed = 0

    for task in asyncio.as_completed(tasks):
        path, size, file_hash, error = await task
        completed += 1

        if error is None:
            hashed_files.append((path, size, file_hash))
        else:
            print(f"읽을 수 없는 파일 제외: {path}")

        print(f"검사 진행률: {completed}/{len(tasks)}", end="\r")

    print()

    grouped_by_hash = defaultdict(list)
    for path, size, file_hash in hashed_files:
        grouped_by_hash[(size, file_hash)].append(path)

    duplicate_groups = []
    for (size, file_hash), paths in grouped_by_hash.items():
        if len(paths) > 1:
            duplicate_groups.append({
                "size": size,
                "hash": file_hash,
                "paths": sorted(paths, key=lambda item: str(item).lower()),
            })

    duplicate_groups.sort(key=lambda group: (-group["size"], str(group["paths"][0]).lower()))
    return duplicate_groups


def print_duplicate_groups(duplicate_groups):
    """중복 파일 그룹을 화면에 출력하고 삭제 선택용 번호를 부여합니다."""
    numbered_files = []

    if not duplicate_groups:
        print("중복 파일이 발견되지 않았습니다.")
        return numbered_files

    print(f"\n중복 파일 그룹 {len(duplicate_groups)}개 발견\n")

    file_number = 1
    for group_index, group in enumerate(duplicate_groups, 1):
        print(f"[그룹 {group_index}]")
        print(f"크기: {format_size(group['size'])}")
        print(f"해시: {group['hash']}")
        print("파일 목록:")

        for path in group["paths"]:
            print(f"  {file_number}. {path}")
            numbered_files.append(path)
            file_number += 1

        print()

    return numbered_files


def parse_number_list(text, max_number):
    """쉼표로 구분된 번호 입력을 정수 목록으로 변환합니다."""
    selected = []

    for raw_value in text.split(","):
        value = raw_value.strip()
        if not value:
            continue

        if not value.isdigit():
            raise ValueError("번호는 숫자로 입력해야 합니다.")

        number = int(value)
        if number < 1 or number > max_number:
            raise ValueError(f"선택 가능한 번호는 1부터 {max_number}까지입니다.")

        if number not in selected:
            selected.append(number)

    return selected


async def delete_selected_files(numbered_files):
    """사용자가 선택한 중복 파일을 확인 후 삭제합니다."""
    if not numbered_files:
        print("삭제할 중복 파일이 없습니다.")
        return

    raw_numbers = await asyncio.to_thread(
        input,
        "삭제할 파일 번호를 입력하세요. 여러 개는 쉼표로 구분합니다. 취소는 빈 값 입력: ",
    )

    if not raw_numbers.strip():
        print("삭제를 취소했습니다.")
        return

    try:
        selected_numbers = parse_number_list(raw_numbers, len(numbered_files))
    except ValueError as error:
        print(error)
        return

    selected_paths = [numbered_files[number - 1] for number in selected_numbers]

    print("\n삭제 예정 파일:")
    for path in selected_paths:
        print(f"- {path}")

    confirm = await asyncio.to_thread(input, "\n정말 삭제할까요? 이 작업은 되돌릴 수 없습니다. (yes/no): ")
    if confirm.strip().lower() != "yes":
        print("삭제를 취소했습니다.")
        return

    deleted_count = 0
    for path in selected_paths:
        try:
            await asyncio.to_thread(path.unlink)
            deleted_count += 1
            print(f"삭제 완료: {path}")
        except OSError as error:
            print(f"삭제 실패: {path} ({error})")

    print(f"삭제된 파일 수: {deleted_count}개")


async def command_loop(duplicate_groups):
    """검사 후 사용자가 결과를 확인, 저장, 삭제할 수 있는 명령 루프입니다."""
    numbered_files = print_duplicate_groups(duplicate_groups)

    while True:
        print("명령어: list, delete, exit")
        command = await asyncio.to_thread(input, "> ")
        command = command.strip().lower()

        if command == "list":
            numbered_files = print_duplicate_groups(duplicate_groups)
        elif command == "delete":
            await delete_selected_files(numbered_files)
        elif command == "exit":
            print("프로그램을 종료합니다.")
            return
        else:
            print("알 수 없는 명령어입니다.")


def build_parser():
    parser = argparse.ArgumentParser(
        description="폴더 안에서 내용이 같은 중복 파일을 찾아주는 CLI 프로그램"
    )
    parser.add_argument(
        "folder",
        nargs="?",
        help="검사할 폴더 경로입니다. 생략하면 실행 중에 입력받습니다.",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="하위 폴더까지 포함해서 검사합니다.",
    )
    parser.add_argument(
        "-c",
        "--concurrency",
        type=int,
        default=4,
        help="동시에 해시를 계산할 최대 파일 수입니다. 기본값은 4입니다.",
    )
    return parser


async def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.concurrency < 1:
        print("concurrency 값은 1 이상이어야 합니다.")
        return

    folder_text = args.folder
    if not folder_text:
        folder_text = await asyncio.to_thread(input, "검사할 폴더 경로를 입력하세요: ")

    folder = normalize_path(folder_text.strip())

    if not folder.exists():
        print(f"존재하지 않는 폴더입니다: {folder}")
        return

    if not folder.is_dir():
        print(f"폴더가 아닙니다: {folder}")
        return

    recursive = args.recursive
    if not args.recursive:
        answer = await asyncio.to_thread(input, "하위 폴더까지 검사할까요? (y/n): ")
        recursive = answer.strip().lower() == "y"

    print(f"검사 폴더: {folder}")
    print(f"하위 폴더 포함: {'예' if recursive else '아니오'}")

    files = await asyncio.to_thread(collect_files, folder, recursive)
    print(f"전체 파일 수: {len(files)}개")

    if len(files) < 2:
        print("비교할 파일이 2개 미만입니다.")
        return

    files_by_size = await asyncio.to_thread(group_files_by_size, files)
    candidate_count = sum(len(paths) for paths in files_by_size.values())

    if candidate_count == 0:
        print("크기가 같은 파일이 없어 중복 파일이 발견되지 않았습니다.")
        return

    print(f"중복 가능성이 있는 파일: {candidate_count}개")
    duplicate_groups = await find_duplicate_groups(files_by_size, args.concurrency)
    await command_loop(duplicate_groups)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n사용자 요청으로 종료했습니다.")
