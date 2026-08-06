#!/usr/bin/env python3

from __future__ import annotations

import shutil
import struct
from pathlib import Path


# Any STL exceeding this size along X, Y, or Z will be scaled down.
MAX_DIMENSION_METRES = 10.0

# Requested scaling: divide coordinates by 100.
# Change this to 1000.0 if millimetres were interpreted as metres.
SCALE_DIVISOR = 10.0

# Corrected models are placed here.
OUTPUT_DIRECTORY = Path("scaled_stl")

# Set this to True to copy already-correct STL files into the output folder.
COPY_UNCHANGED_FILES = False


def is_binary_stl(path: Path) -> bool:
    """
    Detect a binary STL by comparing the declared triangle count with
    the expected binary STL file size.
    """
    file_size = path.stat().st_size

    if file_size < 84:
        return False

    with path.open("rb") as file:
        file.seek(80)
        triangle_count_data = file.read(4)

    if len(triangle_count_data) != 4:
        return False

    triangle_count = struct.unpack("<I", triangle_count_data)[0]
    expected_size = 84 + triangle_count * 50

    return file_size == expected_size


def inspect_binary_stl(path: Path) -> tuple[list[float], list[float]]:
    minimum = [float("inf")] * 3
    maximum = [float("-inf")] * 3

    with path.open("rb") as file:
        header = file.read(80)
        triangle_count_data = file.read(4)

        if len(header) != 80 or len(triangle_count_data) != 4:
            raise ValueError("Invalid binary STL header")

        triangle_count = struct.unpack("<I", triangle_count_data)[0]

        for _ in range(triangle_count):
            triangle_data = file.read(50)

            if len(triangle_data) != 50:
                raise ValueError("Unexpected end of binary STL")

            # 12 floats:
            # normal XYZ, vertex 1 XYZ, vertex 2 XYZ, vertex 3 XYZ
            values = struct.unpack("<12fH", triangle_data)
            vertices = values[3:12]

            for index in range(0, 9, 3):
                for axis in range(3):
                    coordinate = vertices[index + axis]
                    minimum[axis] = min(minimum[axis], coordinate)
                    maximum[axis] = max(maximum[axis], coordinate)

    return minimum, maximum


def scale_binary_stl(source: Path, destination: Path, divisor: float) -> None:
    with source.open("rb") as input_file, destination.open("wb") as output_file:
        header = input_file.read(80)
        triangle_count_data = input_file.read(4)

        if len(header) != 80 or len(triangle_count_data) != 4:
            raise ValueError("Invalid binary STL header")

        triangle_count = struct.unpack("<I", triangle_count_data)[0]

        output_file.write(header)
        output_file.write(triangle_count_data)

        for _ in range(triangle_count):
            triangle_data = input_file.read(50)

            if len(triangle_data) != 50:
                raise ValueError("Unexpected end of binary STL")

            values = list(struct.unpack("<12fH", triangle_data))

            # Leave the normal vector untouched.
            # Scale the nine vertex coordinates.
            for index in range(3, 12):
                values[index] /= divisor

            output_file.write(struct.pack("<12fH", *values))


def inspect_ascii_stl(path: Path) -> tuple[list[float], list[float]]:
    minimum = [float("inf")] * 3
    maximum = [float("-inf")] * 3
    vertex_found = False

    with path.open("r", encoding="utf-8", errors="replace") as file:
        for line in file:
            parts = line.strip().split()

            if len(parts) == 4 and parts[0].lower() == "vertex":
                coordinates = [float(value) for value in parts[1:]]
                vertex_found = True

                for axis, coordinate in enumerate(coordinates):
                    minimum[axis] = min(minimum[axis], coordinate)
                    maximum[axis] = max(maximum[axis], coordinate)

    if not vertex_found:
        raise ValueError("No vertices found in ASCII STL")

    return minimum, maximum


def scale_ascii_stl(source: Path, destination: Path, divisor: float) -> None:
    with (
        source.open("r", encoding="utf-8", errors="replace") as input_file,
        destination.open("w", encoding="utf-8", newline="") as output_file,
    ):
        for line in input_file:
            stripped = line.strip()
            parts = stripped.split()

            if len(parts) == 4 and parts[0].lower() == "vertex":
                coordinates = [float(value) / divisor for value in parts[1:]]
                indentation = line[: len(line) - len(line.lstrip())]

                output_file.write(
                    f"{indentation}vertex "
                    f"{coordinates[0]:.9g} "
                    f"{coordinates[1]:.9g} "
                    f"{coordinates[2]:.9g}\n"
                )
            else:
                output_file.write(line)


def dimensions_from_bounds(
    minimum: list[float],
    maximum: list[float],
) -> tuple[float, float, float]:
    return tuple(
        maximum[axis] - minimum[axis]
        for axis in range(3)
    )


def process_stl(path: Path) -> None:
    binary = is_binary_stl(path)

    if binary:
        minimum, maximum = inspect_binary_stl(path)
    else:
        minimum, maximum = inspect_ascii_stl(path)

    dimensions = dimensions_from_bounds(minimum, maximum)
    requires_scaling = any(
        dimension > MAX_DIMENSION_METRES
        for dimension in dimensions
    )

    dimensions_text = (
        f"{dimensions[0]:.4g} × "
        f"{dimensions[1]:.4g} × "
        f"{dimensions[2]:.4g}"
    )

    destination = OUTPUT_DIRECTORY / path.name

    if requires_scaling:
        if binary:
            scale_binary_stl(path, destination, SCALE_DIVISOR)
        else:
            scale_ascii_stl(path, destination, SCALE_DIVISOR)

        scaled_dimensions = tuple(
            dimension / SCALE_DIVISOR
            for dimension in dimensions
        )

        print(
            f"SCALED  {path.name}\n"
            f"        Before: {dimensions_text} m\n"
            f"        After:  "
            f"{scaled_dimensions[0]:.4g} × "
            f"{scaled_dimensions[1]:.4g} × "
            f"{scaled_dimensions[2]:.4g} m"
        )
    else:
        print(f"OK      {path.name}: {dimensions_text} m")

        if COPY_UNCHANGED_FILES:
            shutil.copy2(path, destination)


def main() -> None:
    stl_files = sorted(
        path
        for path in Path.cwd().iterdir()
        if path.is_file() and path.suffix.lower() == ".stl"
    )

    if not stl_files:
        print("No STL files found in the current directory.")
        return

    OUTPUT_DIRECTORY.mkdir(exist_ok=True)

    print(f"Found {len(stl_files)} STL file(s).")
    print(f"Scaling models larger than {MAX_DIMENSION_METRES:g} m.")
    print(f"Scale divisor: {SCALE_DIVISOR:g}")
    print()

    failures = 0

    for path in stl_files:
        try:
            process_stl(path)
        except (OSError, ValueError, struct.error) as error:
            failures += 1
            print(f"ERROR   {path.name}: {error}")

    print()
    print(f"Finished. Corrected files are in: {OUTPUT_DIRECTORY.resolve()}")

    if failures:
        print(f"{failures} file(s) could not be processed.")


if __name__ == "__main__":
    main()
