"""------------------------------------------------------------------------------------------------
 Project  : Build & Clean Utility for Python Executables

 Date     : 05/06/2025

 Author   : Dhanush K ( u112880 | dhanush.katari@tranetechnologies.com )

 Brief    : This script automates building and cleaning PyInstaller-based Python executables.
            - Takes a Python script as input (after `-b` flag).
            - Generates version info using a YAML file.
            - Builds the executable via PyInstaller.
            - Cleans output directories (`build`, `dist`, `.spec` files) when `-c` flag is used.
---------------------------------------------------------------------------------------------------
 Copyright (c) 2025, Trane Technologies.
 All rights reserved.
---------------------------------------------------------------------------------------------------
 Revision : [ Version - v0.4.0 ] [ Date - 2026-09-03 ] [ Revised by - Dhanush K ]
------------------------------------------------------------------------------------------------"""

import os
import sys
import shutil
import argparse
import subprocess
import yaml
from PIL import Image, UnidentifiedImageError

# -------------------------------------------------------------------------------------------------
#  Constants
# -------------------------------------------------------------------------------------------------


# -------------------------------------------------------------------------------------------------
#  Class Objects
# -------------------------------------------------------------------------------------------------

class BuildUtility:
    """ BuildUtility class for handling build operations """

    def __init__(self, input_script):
        self.input_script = os.path.abspath(input_script)
        self.base_name = os.path.splitext(os.path.basename(self.input_script))[0]
        self.project_root = os.path.dirname(self.input_script)
        self.yaml_file = os.path.join(self.project_root, "metadata.yaml")
        self.logo_file = os.path.join(self.project_root, "icons", "espressif.png")
        self.icon_file = os.path.join(self.project_root, "icons", "exe-file.ico")
        self.icons_folder = os.path.join(self.project_root, "icons")
        self.var_info = f"{self.base_name}_version_info.txt"
        self.build_folder = "build"

        # Ensure the build folder exists
        os.makedirs(self.build_folder, exist_ok=True)

    def generate_version_info(self):
        """ Generate version info file using metadata YAML """
        yaml_file_abs = os.path.abspath(self.yaml_file)

        if not os.path.exists(yaml_file_abs):
            print(f"Error: YAML file '{self.yaml_file}' not found.")
            sys.exit(1)
        if not os.path.exists(self.icon_file):
            print(f"Error: Icon file '{self.icon_file}' not found.")
            sys.exit(1)

        var_info_cmd = [
            sys.executable,
            "-m",
            "pyinstaller_versionfile",
            "--source-format",
            "yaml",
            "--outfile",
            os.path.join(self.build_folder, self.var_info),
            self.yaml_file,
        ]

        try:
            subprocess.run(var_info_cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error: Generating version info file - {e}")
            sys.exit(1)

    def generate_application_icon(self):
        """Generate a multi-resolution ICO from the application logo."""
        if not os.path.exists(self.logo_file):
            print(f"Error: Logo file '{self.logo_file}' not found.")
            sys.exit(1)
        icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        try:
            with Image.open(self.logo_file) as logo:
                logo.convert("RGBA").save(self.icon_file, format="ICO", sizes=icon_sizes)
        except (OSError, UnidentifiedImageError) as error:
            print(f"Error: Generating application icon - {error}")
            sys.exit(1)
        print(f"Info: Generated application icon '{self.icon_file}'.")

    def build_executable(self):
        """ Build the executable using PyInstaller """
        yaml_file_abs = os.path.abspath(self.yaml_file)

        if not os.path.exists(yaml_file_abs):
            print(f"Error: YAML file '{self.yaml_file}' not found.")
            sys.exit(1)

        # Load metadata from YAML
        try:
            with open(self.yaml_file, "r", encoding="utf-8") as f:
                metadata = yaml.safe_load(f)
        except OSError as e:
            print(f"Error: loading YAML file - {e}")
            sys.exit(1)

        exe_name = metadata.get("InternalName", self.base_name).strip()
        if not exe_name:
            print("Error: InternalName is missing or empty in metadata.")
            sys.exit(1)

        pyinstaller_cmd = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--onefile",
            "--add-data",
            f"{self.yaml_file};.",
            "--add-data",
            f"{self.icons_folder};icons",
            "--collect-data",
            "esptool",
            "--icon",
            self.icon_file,
            "--version-file",
            os.path.join(self.build_folder, self.var_info),
            "--name",
            exe_name,
            self.input_script,
        ]

        try:
            subprocess.run(pyinstaller_cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error: Building executable - {e}")
            sys.exit(1)

        print("Info: Executable build process completed successfully!")

class CleanUtility:
    """ CleanUtility class for cleaning project directories """

    @staticmethod
    def clean_project():
        """ Remove build artifacts and directories """
        folders_to_delete = ["build", "dist"]
        files_to_delete = [f for f in os.listdir('.') if f.endswith('.spec')]

        for folder in folders_to_delete:
            if os.path.exists(folder):
                shutil.rmtree(folder)
                print(f"Info: Deleted {folder} folder.")

        for file in files_to_delete:
            os.remove(file)
            print(f"Info: Deleted {file} file.")

        print("Info: Clean-up completed!")

    @staticmethod
    def print_summary():
        """ Print cleanup summary """
        print("Clean-up process finished.")


# -------------------------------------------------------------------------------------------------
#  Main
# -------------------------------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Utility script for building and cleaning Python executables.")
    parser.add_argument(
        "-b", "--build", type=str, help="Build the project with the specified input script.")
    parser.add_argument("-c", "--clean", action="store_true", help="Clean the project.")

    args = parser.parse_args()

    if args.clean:
        CleanUtility.clean_project()
    if args.build:
        build_util = BuildUtility(args.build)
        build_util.generate_application_icon()
        build_util.generate_version_info()
        build_util.build_executable()

# --------------------------------------------------------------------------------------------------
#  End of file
# --------------------------------------------------------------------------------------------------
