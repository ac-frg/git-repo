# Copyright (C) 2026 The Android Open Source Project
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

"""Unittests for the subcmds/rebase.py module."""

from unittest import mock

from error import GitError
from subcmds import rebase


def test_resolve_onto_manifest_success() -> None:
    """Test _ResolveOntoManifest when ToLocal succeeds."""
    project = mock.MagicMock()
    project.revisionExpr = "main"

    remote = mock.MagicMock()
    remote.ToLocal.return_value = "refs/remotes/goog/main"
    project.GetRemote.return_value = remote

    res = rebase._ResolveOntoManifest(project)
    assert res == "refs/remotes/goog/main"
    project.GetRemote.assert_called_once()
    remote.ToLocal.assert_called_once_with("main")


def test_resolve_onto_manifest_fallback() -> None:
    """Test _ResolveOntoManifest when ToLocal raises GitError."""
    project = mock.MagicMock()
    project.revisionExpr = "main"

    remote = mock.MagicMock()
    remote.ToLocal.side_effect = GitError("Failed to resolve")
    project.GetRemote.return_value = remote

    res = rebase._ResolveOntoManifest(project)
    assert res == "main"
    project.GetRemote.assert_called_once()
    remote.ToLocal.assert_called_once_with("main")
