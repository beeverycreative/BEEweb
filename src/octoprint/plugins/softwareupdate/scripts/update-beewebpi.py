#!/bin/env python
from __future__ import absolute_import

from distutils.dir_util import copy_tree
from distutils.file_util import copy_file
from octoprint.settings import settings
import errno
import subprocess
import sys
import os

def _get_git_executables():
	GITS = ["git"]
	if sys.platform == "win32":
		GITS = ["git.cmd", "git.exe", "..\\Git\\bin\\git.exe"]
	return GITS


def _git(args, cwd, hide_stderr=False, verbose=False, git_executable=None):
	if git_executable is not None:
		commands = [git_executable]
	else:
		commands = _get_git_executables()

	for c in commands:
		try:
			p = subprocess.Popen([c] + args, cwd=cwd, stdout=subprocess.PIPE,
			                     stderr=(subprocess.PIPE if hide_stderr
			                             else None))
			break
		except EnvironmentError:
			e = sys.exc_info()[1]
			if e.errno == errno.ENOENT:
				continue
			if verbose:
				print("unable to run %s" % args[0])
				print(e)
			return None, None
	else:
		if verbose:
			print("unable to find command, tried %s" % (commands,))
		return None, None

	stdout = p.communicate()[0].strip()
	if sys.version >= '3':
		stdout = stdout.decode()

	if p.returncode != 0:
		if verbose:
			print("unable to run %s (error)" % args[0])

	return p.returncode, stdout

def _rescue_changes(git_executable, folder):
	print(">>> Running: git diff --shortstat")
	returncode, stdout = _git(["diff", "--shortstat"], folder, git_executable=git_executable)
	if returncode != 0:
		raise RuntimeError("Could not update, \"git diff\" failed with returncode %d: %s" % (returncode, stdout))
	if stdout and stdout.strip():
		# we got changes in the working tree, maybe from the user, so we'll now rescue those into a patch
		import time
		import os
		timestamp = time.strftime("%Y%m%d%H%M")
		patch = os.path.join(folder, "%s-preupdate.patch" % timestamp)

		print(">>> Running: git diff and saving output to %s" % timestamp)
		returncode, stdout = _git(["diff"], folder, git_executable=git_executable)
		if returncode != 0:
			raise RuntimeError("Could not update, installation directory was dirty and state could not be persisted as a patch to %s" % patch)

		with open(patch, "wb") as f:
			f.write(stdout)

		return True

	return False


def update_source(git_executable, folder, target, force=False, branch=None):
	if _rescue_changes(git_executable, folder):
		print(">>> Running: git reset --hard")
		returncode, stdout = _git(["reset", "--hard"], folder, git_executable=git_executable)
		if returncode != 0:
			raise RuntimeError("Could not update, \"git reset --hard\" failed with returncode %d: %s" % (returncode, stdout))

	print(">>> Running: git fetch")
	returncode, stdout = _git(["fetch"], folder, git_executable=git_executable)
	if returncode != 0:
		raise RuntimeError("Could not update, \"git fetch\" failed with returncode %d: %s" % (returncode, stdout))
	print(stdout)

	if branch is not None and branch.strip() != "":
		print(">>> Running: git checkout {}".format(branch))
		returncode, stdout = _git(["checkout", branch], folder, git_executable=git_executable)
		if returncode != 0:
			raise RuntimeError("Could not update, \"git checkout\" failed with returncode %d: %s" % (returncode, stdout))

	print(">>> Running: git pull")
	returncode, stdout = _git(["pull"], folder, git_executable=git_executable)
	if returncode != 0:
		raise RuntimeError("Could not update, \"git pull\" failed with returncode %d: %s" % (returncode, stdout))
	print(stdout)

	if force:
		reset_command = ["reset", "--hard"]
		reset_command += [target]

		print(">>> Running: git %s" % " ".join(reset_command))
		returncode, stdout = _git(reset_command, folder, git_executable=git_executable)
		if returncode != 0:
			raise RuntimeError("Error while updating, \"git %s\" failed with returncode %d: %s" % (" ".join(reset_command), returncode, stdout))
		print(stdout)

## CUSTOM FUNCTIONS ##
def install_support_files(folder, target_folder):
	print(">>> Copying BEEweb settings files to installation directory...")
	settings_folder_path = folder + '/src/filesystem/home/pi/.beeweb'

	try:
		# creates a backup of the user config.yaml and users.yaml file
		copy_file(target_folder + '/config.yaml', target_folder + '/config-backup.yaml')
		if os.path.exists(target_folder + '/users.yaml'):
			copy_file(target_folder + '/users.yaml', target_folder + '/users-backup.yaml')

		files_copied = copy_tree(settings_folder_path, target_folder)

		# overwrites the settings file from the repository with the backup
		copy_file(target_folder + '/config-backup.yaml', target_folder + '/config.yaml')
		if os.path.exists(target_folder + '/users-backup.yaml'):
			copy_file(target_folder + '/users-backup.yaml', target_folder + '/users.yaml')

	except Exception as ex:
		raise RuntimeError(
			"Could not update, copying the files to .beeweb directory failed with error: %s" % ex.message)
	finally:
		if files_copied:
			print("BEEweb settings files copied!")

	if sys.platform != "win32" and sys.platform != "darwin":
		try:
			# copies the files in the /etc directory
			copy_tree(folder + '/src/filesystem/root/etc/default', '/etc/default')
			copy_tree(folder + '/src/filesystem/root/etc/haproxy', '/etc/haproxy')
			copy_tree(folder + '/src/filesystem/root/etc/init.d', '/etc/init.d')
			copy_tree(folder + '/src/filesystem/root/etc/init.d', '/etc/hostapd')

		except Exception as ex:
			raise RuntimeError(
				"Could not update, copying the system files to /etc directories failed with error: %s" % ex.message)
		finally:
			if files_copied:
				print("BEEwebPi system files copied!")

def parse_arguments():
	import argparse
	boolean_trues = ["true", "yes", "1"]
	boolean_falses = ["false", "no", "0"]

	parser = argparse.ArgumentParser(prog="update-beewebpi.py")

	parser.add_argument("--git", action="store", type=str, dest="git_executable",
	                    help="Specify git executable to use")
	parser.add_argument("--force", action="store", type=lambda x: x in boolean_trues,
	                    dest="force", default=False,
	                    help="Set this to true to force the update to only the specified version (nothing newer, nothing older)")
	parser.add_argument("folder", type=str,
	                    help="Specify the base folder of the BEESOFT configurations installation to update")
	parser.add_argument("target", type=str,
	                    help="Specify the commit or tag to which to update")
	parser.add_argument("branch", type=str,
	                    help="Specify the branch from which to install the update")
	args = parser.parse_args()

	return args

def main():
	args = parse_arguments()

	git_executable = None
	if args.git_executable:
		git_executable = args.git_executable

	folder = args.folder
	target = args.target
	branch = args.branch

	import os
	if not os.access(folder, os.W_OK):
		raise RuntimeError("Could not update, base folder is not writable")

	# folder where the installation settings files are located
	target_folder = settings(init=True).getBaseFolder('base')

	update_source(git_executable, folder, target, force=args.force, branch=branch)
	install_support_files(folder, target_folder)

if __name__ == "__main__":
	main()
