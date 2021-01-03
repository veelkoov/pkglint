#!/usr/bin/python3

from __future__ import annotations  # ...RLY?

import glob
import re
from typing import Final

LOCAL_DB_DIR_PATH = '/var/lib/pacman/local'  # TODO: Parametrize
WANTED_PKGS_LIST_PATH = './wanted.txt'  # TODO: Parametrize


class DuplicationError(RuntimeError):
    @classmethod
    def package(cls, package: Package) -> DuplicationError:
        return cls(f"Package name '{package.name}' duplicated")

    @classmethod
    def section(cls, file_path: str, name: str) -> DuplicationError:
        return cls(f"Duplicate section '{name}' in '{file_path}'")


class Package:
    SECTION_NAME: Final[str] = '%NAME%'
    SECTION_VERSION: Final[str] = '%VERSION%'
    SECTION_DESC: Final[str] = '%DESC%'
    SECTION_DEPENDS: Final[str] = '%DEPENDS%'
    SECTION_PROVIDES: Final[str] = '%PROVIDES%'

    __desc_file_path: str
    __name: str
    __version: str
    __desc: str
    __depends: list[str]
    __provides: list[str]
    __wanted: bool

    def __init__(self, desc_file_path: str):
        sections = self.__read_sections_from(desc_file_path)

        self.__desc_file_path = desc_file_path
        self.__name = sections[self.SECTION_NAME][0]
        self.__version = sections[self.SECTION_VERSION][0]
        self.__desc = sections[self.SECTION_DESC][0]

        self.__depends = self.__strip_versions(sections.get(self.SECTION_DEPENDS) or [])
        self.__provides = self.__strip_versions(sections.get(self.SECTION_PROVIDES) or [])

        self.__wanted = False

    @property
    def desc_file_path(self) -> str:
        return self.__desc_file_path

    @property
    def name(self) -> str:
        return self.__name

    @property
    def version(self) -> str:
        return self.__version

    @property
    def desc(self) -> str:
        return self.__desc

    @property
    def depends(self) -> list[str]:
        return self.__depends

    @property
    def provides(self) -> list[str]:
        return self.__provides

    @property
    def wanted(self) -> bool:
        return self.__wanted

    def mark_wanted(self) -> None:
        self.__wanted = True

    @staticmethod
    def __read_sections_from(file_path) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}

        with open(file_path, 'r') as file:
            raw_sections = [section.strip() for section in re.split(r'\n(?=%[A-Z]+%)', file.read())]

        for raw_section in raw_sections:
            items = raw_section.split("\n")
            name = items.pop(0)

            if name in result:
                raise DuplicationError.section(file_path, name)

            result[name] = items

        return result

    def __str__(self) -> str:
        return f"{self.name} {self.version} ({self.desc_file_path})"

    @staticmethod
    def __strip_versions(items: list[str]) -> list[str]:
        return [re.sub(r'[<>=]{1,2}.+$', '', item) for item in items]


class Packages:
    __by_name: dict[str, Package]
    __by_provides: dict[str, list[Package]]

    def __init__(self):
        self.__by_name = {}
        self.__by_provides = {}

    def add(self, package: Package) -> None:
        if package.name in self.__by_name:
            raise DuplicationError.package(package)

        self.__by_name[package.name] = package

        for provided in package.provides:
            if provided not in self.__by_provides:
                self.__by_provides[provided] = []

            self.__by_provides[provided].append(package)

    def mark_wanted_by_name(self, package_name: str) -> bool:
        if package_name not in self.__by_name:
            return False

        package = self.__by_name[package_name]

        if not package.wanted:
            package.mark_wanted()

            for dep_name in package.depends:
                if not self.mark_wanted_by_name(dep_name) and not self.__mark_wanted_by_provided(dep_name):
                    raise LookupError(f"'{dep_name}' required by {package.name} is not installed, nor provided")

        return True

    def __mark_wanted_by_provided(self, provided_name: str) -> bool:
        if provided_name not in self.__by_provides:
            return False

        for package in self.__by_provides[provided_name]:
            self.mark_wanted_by_name(package.name)

        return True

    def get_unwanted(self) -> list[Package]:
        return [package for package in self.__by_name.values() if not package.wanted]


class LocalPackageDatabase:
    __db_dir_path: str

    def __init__(self, db_dir_path: str):
        self.__db_dir_path = db_dir_path

    def read(self) -> Packages:
        result = Packages()

        for file_path in glob.glob(f"{self.__db_dir_path}/*/desc"):
            package = Package(file_path)
            result.add(package)

        return result


class UserWantsList:
    __items: list[str]

    def __init__(self, file_path: str):
        with open(file_path, 'r') as file:
            self.__items = [line for line in file.read().splitlines() if '' != line.strip()]

    @property
    def items(self) -> list[str]:
        return self.__items


def process() -> None:
    packages = LocalPackageDatabase(LOCAL_DB_DIR_PATH).read()

    for wanted_pkg_name in UserWantsList(WANTED_PKGS_LIST_PATH).items:
        if not packages.mark_wanted_by_name(wanted_pkg_name):
            raise LookupError(f"'{wanted_pkg_name}' is not installed")

    for package in packages.get_unwanted():
        print(f"{package.name} - {package.desc}")


if __name__ == '__main__':
    process()
