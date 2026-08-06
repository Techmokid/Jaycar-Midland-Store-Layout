from pathlib import Path
import sys

import trimesh


def main() -> None:
    # Folder containing this script:
    # ...\Assets\STLs
    stl_folder = Path(__file__).resolve().parent

    # Sibling folder:
    # ...\Assets\OBJs
    obj_folder = stl_folder.parent / "OBJs"
    obj_folder.mkdir(parents=True, exist_ok=True)

    stl_files = sorted(
        path
        for path in stl_folder.iterdir()
        if path.is_file() and path.suffix.lower() == ".stl"
    )

    if not stl_files:
        print(f"No STL files found in:\n{stl_folder}")
        return

    print(f"Input folder:  {stl_folder}")
    print(f"Output folder: {obj_folder}")
    print(f"Found {len(stl_files)} STL file(s).\n")

    successful = 0
    failed = 0

    for stl_path in stl_files:
        obj_path = obj_folder / f"{stl_path.stem}.obj"

        try:
            print(f"Converting: {stl_path.name}")

            mesh = trimesh.load_mesh(
                stl_path,
                file_type="stl",
                process=False,
            )

            if mesh.is_empty:
                raise ValueError("The STL contains no geometry.")

            mesh.export(obj_path, file_type="obj")

            print(f"       Saved: {obj_path.name}")
            successful += 1

        except Exception as error:
            print(f"       FAILED: {error}")
            failed += 1

    print("\nConversion complete.")
    print(f"Successful: {successful}")
    print(f"Failed:     {failed}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nFatal error: {error}")
        sys.exit(1)
