# Copyright (C) 2024 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from typing import Set

from command import Command
import platform_utils


class Gc(Command):
    COMMON = True
    helpSummary = "Cleaning up internal repo state."
    helpUsage = """
%prog
"""

    def _find_git_to_delete(
        self, to_keep: Set[str], start_dir: str
    ) -> Set[str]:
        """Searches no longer needed ".git" directories.

        Scans the file system starting from `start_dir` and removes all
        directories that end with ".git" that are not in the `to_keep` set."""
        to_delete = set()
        for root, dirs, _ in platform_utils.walk(start_dir):
            for directory in dirs:
                if not directory.endswith(".git"):
                    continue

                path = os.path.join(root, directory)
                if path not in to_keep:
                    to_delete.add(path)

        return to_delete

    def Execute(self, opt, args):
        projects = self.GetProjects(
            args, all_manifests=not opt.this_manifest_only
        )
        print(f"Scanning filesystem under {self.repodir}...")

        project_paths = set()
        project_object_paths = set()

        for project in projects:
            project_paths.add(project.gitdir)
            project_object_paths.add(project.objdir)

        to_delete = self._find_git_to_delete(
            project_paths, os.path.join(self.repodir, "projects")
        )

        to_delete.update(
            self._find_git_to_delete(
                project_object_paths,
                os.path.join(self.repodir, "project-objects"),
            )
        )

        if not to_delete:
            print("Nothing to clean up.")
            return

        print("Identified the following projects are no longer used:")
        print("\n".join(to_delete))
        print("\n")
        print(
            "If you proceed, any local commits in those projects will be "
            "destroyed!"
        )
        ask = input("Proceed? [y/N] ")
        if ask.lower() != "y":
            return 1

        for path in to_delete:
            platform_utils.rmtree(path)
