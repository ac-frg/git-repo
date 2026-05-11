# Copyright (C) 2012 The Android Open Source Project
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

from collections import namedtuple
import functools
import io
import optparse

from color import Coloring
from command import DEFAULT_LOCAL_JOBS, PagedCommand
from git_refs import R_HEADS
from git_refs import R_M
BranchInfo = namedtuple('BranchInfo', ['relpath', 'name', 'commits', 'date', 'is_current'])


class _Coloring(Coloring):
    def __init__(self, config):
        Coloring.__init__(self, config, "status")


class Info(PagedCommand):
    COMMON = True
    PARALLEL_JOBS = DEFAULT_LOCAL_JOBS
    helpSummary = (
        "Get info on the manifest branch, current branch or unmerged branches"
    )
    helpUsage = "%prog [-dl] [-o [-c]] [<project>...]"

    def _Options(self, p):
        p.add_option(
            "-d",
            "--diff",
            dest="all",
            action="store_true",
            help="show full info and commit diff including remote branches",
        )
        p.add_option(
            "-o",
            "--overview",
            action="store_true",
            help="show overview of all local commits",
        )
        p.add_option(
            "-c",
            "--current-branch",
            action="store_true",
            help="consider only checked out branches",
        )
        p.add_option(
            "--no-current-branch",
            dest="current_branch",
            action="store_false",
            help="consider all local branches",
        )
        # Turn this into a warning & remove this someday.
        p.add_option(
            "-b",
            dest="current_branch",
            action="store_true",
            help=optparse.SUPPRESS_HELP,
        )
        p.add_option(
            "-l",
            "--local-only",
            dest="local",
            action="store_true",
            help="disable all remote operations",
        )

    def Execute(self, opt, args):
        self.out = _Coloring(self.client.globalConfig)
        self.heading = self.out.printer("heading", attr="bold")
        self.headtext = self.out.nofmt_printer("headtext", fg="yellow")
        self.redtext = self.out.printer("redtext", fg="red")
        self.sha = self.out.printer("sha", fg="yellow")
        self.text = self.out.nofmt_printer("text")
        self.dimtext = self.out.printer("dimtext", attr="dim")

        self.opt = opt

        if not opt.this_manifest_only:
            self.manifest = self.manifest.outer_client
        manifestConfig = self.manifest.manifestProject.config
        mergeBranch = manifestConfig.GetBranch("default").merge
        manifestGroups = self.manifest.GetManifestGroupsStr()

        self.heading("Manifest branch: ")
        if self.manifest.default.revisionExpr:
            self.headtext(self.manifest.default.revisionExpr)
        self.out.nl()
        self.heading("Manifest merge branch: ")
        # The manifest might not have a merge branch if it isn't in a git repo,
        # e.g. if `repo init --standalone-manifest` is used.
        self.headtext(mergeBranch or "")
        self.out.nl()
        self.heading("Manifest groups: ")
        self.headtext(manifestGroups)
        self.out.nl()
        sp = self.manifest.superproject
        srev = sp.commit_id if sp and sp.commit_id else "None"
        self.heading("Superproject revision: ")
        self.headtext(srev)
        self.out.nl()

        self.printSeparator()

        if not opt.overview:
            self._printDiffInfo(opt, args)
        else:
            self._printCommitOverview(opt, args)

    def printSeparator(self):
        self.text("----------------------------")
        self.out.nl()

    @classmethod
    def _DiffHelper(cls, project_idx, opt):
        buf = io.StringIO()
        project = cls.get_parallel_context()["projects"][project_idx]
        config = cls.get_parallel_context()["config"]

        out = _Coloring(config)
        out.redirect(buf)

        heading = out.printer("heading", attr="bold")
        headtext = out.nofmt_printer("headtext", fg="yellow")
        redtext = out.printer("redtext", fg="red")
        sha = out.printer("sha", fg="yellow")
        text = out.nofmt_printer("text")
        dimtext = out.printer("dimtext", attr="dim")

        heading("Project: ")
        headtext(project.name)
        out.nl()

        heading("Mount path: ")
        headtext(project.worktree)
        out.nl()

        heading("Current revision: ")
        headtext(project.GetRevisionId())
        out.nl()

        currentBranch = project.CurrentBranch
        if currentBranch:
            heading("Current branch: ")
            headtext(currentBranch)
            out.nl()

        heading("Manifest revision: ")
        headtext(project.revisionExpr)
        out.nl()

        localBranches = list(project.GetBranches().keys())
        heading("Local Branches: ")
        redtext(str(len(localBranches)))
        if localBranches:
            text(" [")
            text(", ".join(localBranches))
            text("]")
        out.nl()

        if opt.all:
            if not opt.local:
                project.Sync_NetworkHalf(quiet=True, current_branch_only=True)

            branch = project.manifest.manifestProject.config.GetBranch("default").merge
            if branch.startswith(R_HEADS):
                branch = branch[len(R_HEADS) :]
            logTarget = R_M + branch

            bareTmp = project.bare_git._bare
            project.bare_git._bare = False
            localCommits = project.bare_git.rev_list(
                "--abbrev=8",
                "--abbrev-commit",
                "--pretty=oneline",
                logTarget + "..",
                "--",
            )

            originCommits = project.bare_git.rev_list(
                "--abbrev=8",
                "--abbrev-commit",
                "--pretty=oneline",
                ".." + logTarget,
                "--",
            )
            project.bare_git._bare = bareTmp

            heading("Local Commits: ")
            redtext(str(len(localCommits)))
            dimtext(" (on current branch)")
            out.nl()

            for c in localCommits:
                split = c.split()
                sha(split[0] + " ")
                text(" ".join(split[1:]))
                out.nl()

            text("----------------------------")
            out.nl()

            heading("Remote Commits: ")
            redtext(str(len(originCommits)))
            out.nl()

            for c in originCommits:
                split = c.split()
                sha(split[0] + " ")
                text(" ".join(split[1:]))
                out.nl()

        text("----------------------------")
        out.nl()

        return buf.getvalue()

    def _printDiffInfo(self, opt, args):
        projs = self.GetProjects(args, all_manifests=not opt.this_manifest_only)

        def _ProcessResults(_pool, _output, results):
            for output in results:
                if output:
                    print(output, end="")

        with self.ParallelContext():
            self.get_parallel_context()["projects"] = projs
            self.get_parallel_context()["config"] = self.manifest.manifestProject.config

            self.ExecuteInParallel(
                opt.jobs,
                functools.partial(self._DiffHelper, opt=opt),
                range(len(projs)),
                callback=_ProcessResults,
                ordered=True,
                chunksize=1,
            )

    @classmethod
    def _OverviewHelper(cls, project_idx, opt):
        project = cls.get_parallel_context()["projects"][project_idx]

        branches = []
        br = [project.GetUploadableBranch(x) for x in project.GetBranches()]
        br = [x for x in br if x]
        if opt.current_branch:
            br = [x for x in br if x.name == project.CurrentBranch]

        for b in br:
            branches.append(BranchInfo(
                relpath=project.RelPath(local=opt.this_manifest_only),
                name=b.name,
                commits=b.commits,
                date=b.date,
                is_current=b.name == project.CurrentBranch
            ))
        return branches

    def _printCommitOverview(self, opt, args):
        projs = self.GetProjects(args, all_manifests=not opt.this_manifest_only)

        all_branches = []

        def _ProcessResults(_pool, _output, results):
            for branches in results:
                all_branches.extend(branches)

        with self.ParallelContext():
            self.get_parallel_context()["projects"] = projs

            self.ExecuteInParallel(
                opt.jobs,
                functools.partial(self._OverviewHelper, opt=opt),
                range(len(projs)),
                callback=_ProcessResults,
                ordered=True,
                chunksize=1,
            )

        if not all_branches:
            return

        self.out.nl()
        self.heading("Projects Overview")
        current_relpath = None

        for branch in all_branches:
            if current_relpath != branch.relpath:
                current_relpath = branch.relpath
                self.out.nl()
                self.headtext(current_relpath)
                self.out.nl()

            commits = branch.commits
            date = branch.date
            self.text(
                "%s %-33s (%2d commit%s, %s)"
                % (
                    branch.is_current and "*" or " ",
                    branch.name,
                    len(commits),
                    len(commits) != 1 and "s" or "",
                    date,
                )
            )
            self.out.nl()

            for commit in commits:
                split = commit.split()
                self.text(f"{'':38}{'-'} ")
                self.sha(split[0] + " ")
                self.text(" ".join(split[1:]))
                self.out.nl()
