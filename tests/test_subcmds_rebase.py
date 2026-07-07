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

import pytest

from error import GitError
from subcmds import rebase


@pytest.fixture
def cmd() -> rebase.Rebase:
    """Fixture to provide a Rebase command instance with mocked manifest."""
    cmd = rebase.Rebase()
    cmd.manifest = mock.MagicMock()
    cmd.manifest.manifestProject.config = mock.MagicMock()
    cmd.git_event_log = mock.MagicMock()
    return cmd


@mock.patch("subcmds.rebase.GitCommand")
def test_rebase_onto_manifest_success(
    mock_git_command, cmd: rebase.Rebase
) -> None:
    """Test rebase --onto-manifest when ToLocal succeeds."""
    opt, _ = cmd.OptionParser.parse_args(["-m"])
    cmd.CommonValidateOptions(opt, [])
    opt.this_manifest_only = True

    # Setup mocked project
    project = mock.MagicMock()
    project.CurrentBranch = "feature-branch"
    project.revisionExpr = "main"
    project.RelPath.return_value = "project-path"

    # Mock remote and ToLocal
    remote = mock.MagicMock()
    remote.ToLocal.return_value = "refs/remotes/goog/main"
    project.GetRemote.return_value = remote

    # Mock upbranch
    upbranch = mock.MagicMock()
    upbranch.LocalMerge = "refs/remotes/goog/main"
    project.GetBranch.return_value = upbranch

    # Setup command to return the mocked project
    with mock.patch.object(cmd, "GetProjects", return_value=[project]):
        # Mock GitCommand wait
        git_command_instance = mock.MagicMock()
        git_command_instance.Wait.return_value = 0
        mock_git_command.return_value = git_command_instance

        res = cmd.Execute(opt, [])
        assert res == 0

        # Assert GitCommand was called with --onto refs/remotes/goog/main
        mock_git_command.assert_called_once_with(
            project,
            [
                "rebase",
                "--onto",
                "refs/remotes/goog/main",
                "refs/remotes/goog/main",
            ],
        )


@mock.patch("subcmds.rebase.GitCommand")
def test_rebase_onto_manifest_fallback(
    mock_git_command, cmd: rebase.Rebase
) -> None:
    """Test rebase --onto-manifest when ToLocal raises GitError.

    Fallback to revisionExpr.
    """
    opt, _ = cmd.OptionParser.parse_args(["-m"])
    cmd.CommonValidateOptions(opt, [])
    opt.this_manifest_only = True

    project = mock.MagicMock()
    project.CurrentBranch = "feature-branch"
    project.revisionExpr = "main"
    project.RelPath.return_value = "project-path"

    # Mock remote ToLocal raising GitError
    remote = mock.MagicMock()
    remote.ToLocal.side_effect = GitError("Failed to resolve")
    project.GetRemote.return_value = remote

    upbranch = mock.MagicMock()
    upbranch.LocalMerge = "refs/remotes/goog/main"
    project.GetBranch.return_value = upbranch

    with mock.patch.object(cmd, "GetProjects", return_value=[project]):
        git_command_instance = mock.MagicMock()
        git_command_instance.Wait.return_value = 0
        mock_git_command.return_value = git_command_instance

        res = cmd.Execute(opt, [])
        assert res == 0

        # Assert GitCommand was called with fallback --onto main
        mock_git_command.assert_called_once_with(
            project, ["rebase", "--onto", "main", "refs/remotes/goog/main"]
        )


@mock.patch("subcmds.rebase.GitCommand")
def test_rebase_no_onto_manifest(mock_git_command, cmd: rebase.Rebase) -> None:
    """Test rebase without --onto-manifest."""
    opt, _ = cmd.OptionParser.parse_args([])
    cmd.CommonValidateOptions(opt, [])
    opt.this_manifest_only = True

    project = mock.MagicMock()
    project.CurrentBranch = "feature-branch"
    project.revisionExpr = "main"
    project.RelPath.return_value = "project-path"

    upbranch = mock.MagicMock()
    upbranch.LocalMerge = "refs/remotes/goog/main"
    project.GetBranch.return_value = upbranch

    with mock.patch.object(cmd, "GetProjects", return_value=[project]):
        git_command_instance = mock.MagicMock()
        git_command_instance.Wait.return_value = 0
        mock_git_command.return_value = git_command_instance

        res = cmd.Execute(opt, [])
        assert res == 0

        # Assert GitCommand was called without --onto
        mock_git_command.assert_called_once_with(
            project, ["rebase", "refs/remotes/goog/main"]
        )
