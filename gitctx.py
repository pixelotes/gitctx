#!/usr/bin/env python3
"""
gitctx - Git Profile Manager
A CLI tool for managing multiple git profiles with configurations.
"""

import os
import sys
import json
import shutil
import subprocess
import argparse
from pathlib import Path
from typing import Dict, List, Optional

class GitCtx:
    def __init__(self):
        self.config_dir = Path.home() / '.config' / 'gitctx'
        self.profiles_dir = self.config_dir / 'profiles'
        self.repo_dir = self.config_dir
        self.metadata_file = self.config_dir / 'metadata.json'

    def initialize_repo(self, repo_url: Optional[str] = None):
        """Initialize the gitctx configuration repository."""
        if self.config_dir.exists():
            print(f"✅ gitctx repository already exists at {self.config_dir}")
            return
        
        if repo_url:
            # Clone existing repository
            try:
                subprocess.run(['git', 'clone', repo_url, str(self.config_dir)], check=True, capture_output=True)
                print(f"✅ Cloned gitctx repository from {repo_url} to {self.config_dir}")
                
                # 👇 Immediately unset active_profile to avoid accidental overwrites
                metadata = self._load_metadata()
                metadata['active_profile'] = None
                self._save_metadata(metadata)
                self._commit_changes("Unset active profile after clone")
                print("⚠️  Active profile unset to avoid accidental overwrites")
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to clone repository: {e}")
                return
        else:
            # Create new repository
            self.config_dir.mkdir(parents=True)
            self.profiles_dir.mkdir()
            
            # Initialize git repo
            subprocess.run(['git', 'init'], cwd=self.config_dir, check=True, capture_output=True)
            
            # Create initial metadata
            metadata = {
                'version': '1.0',
                'profiles': {},
                'active_profile': None
            }
            self._save_metadata(metadata)
            
            # Create .gitignore
            gitignore_content = """# gitctx generated files
    *.tmp
    *.backup
    """
            (self.config_dir / '.gitignore').write_text(gitignore_content)
            
            # Initial commit
            subprocess.run(['git', 'add', '.'], cwd=self.config_dir, check=True, capture_output=True)
            subprocess.run(['git', 'commit', '-m', 'Initial gitctx setup'], 
                        cwd=self.config_dir, check=True, capture_output=True)
            
            print(f"✅ Initialized gitctx repository at {self.config_dir}")

    
    def _save_metadata(self, metadata: Dict):
        """Save metadata to file."""
        with open(self.metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def _load_metadata(self) -> Dict:
        """Load metadata from file."""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        return {'version': '1.0', 'profiles': {}, 'active_profile': None}
    
    def _commit_changes(self, message: str):
        """Commit changes to the config repository."""
        try:
            subprocess.run(['git', 'add', '.'], cwd=self.config_dir, check=True, capture_output=True)
            subprocess.run(['git', 'commit', '-m', message], 
                         cwd=self.config_dir, check=True, capture_output=True)
            print(f"✅ Committed: {message}")
        except subprocess.CalledProcessError:
            print("ℹ️  No changes to commit")
    
    def _get_fzf_selection(self, options: List[str], prompt: str = "Select profile") -> Optional[str]:
        """Use fzf for selection if available, otherwise use simple input."""
        if not options:
            return None
            
        # Check if fzf is available
        try:
            subprocess.run(['which', 'fzf'], check=True, capture_output=True)
            use_fzf = True
        except subprocess.CalledProcessError:
            use_fzf = False
        
        if use_fzf:
            try:
                process = subprocess.Popen(
                    ['fzf', '--prompt', f'{prompt}: ', '--height', '40%'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=None,  # Let stderr go to terminal
                    text=True
                )
                stdout, _ = process.communicate('\n'.join(options))
                if process.returncode == 0 and stdout.strip():
                    return stdout.strip()
                elif process.returncode == 130:  # Ctrl+C in fzf
                    return None
                return None
            except Exception:
                use_fzf = False
        
        if not use_fzf:
            print(f"\n{prompt}:")
            for i, option in enumerate(options, 1):
                print(f"  {i}. {option}")
            try:
                choice = input(f"\nEnter choice (1-{len(options)}): ").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            except (ValueError, KeyboardInterrupt):
                pass
        return None
    
    def add_new_profile(self, profile_name: str, name: str, email: str):
        """Add a new git profile from scratch."""
        profile_dir = self.profiles_dir / profile_name
        if profile_dir.exists():
            print(f"❌ Profile '{profile_name}' already exists")
            return
        
        profile_dir.mkdir()
        
        # Create minimal gitconfig
        gitconfig_content = f"""[user]
        name = {name}
        email = {email}

    [init]
        defaultBranch = main

    [push]
        default = simple

    [pull]
        rebase = false

    [core]
        editor = vim
        autocrlf = false
    """
        
        (profile_dir / 'gitconfig').write_text(gitconfig_content)
        
        # Update metadata
        metadata = self._load_metadata()
        metadata['profiles'][profile_name] = {
            'type': 'new',
            'created_at': subprocess.check_output(['date', '-Iseconds']).decode().strip(),
            'user_name': name,
            'user_email': email,
            'files': {
                'gitconfig': '.gitconfig'  # Store as relative path
            }
        }
        self._save_metadata(metadata)
        
        self._commit_changes(f"Add new profile: {profile_name}")
        print(f"✅ Created new profile '{profile_name}'")
    
    def remove_profile(self, profile_name: str = None):
        """Remove a git profile."""
        metadata = self._load_metadata()
        profiles = list(metadata['profiles'].keys())
        
        if not profiles:
            print("❌ No profiles found")
            return
        
        if not profile_name:
            profile_name = self._get_fzf_selection(profiles, "Select profile to remove")
        
        if not profile_name or profile_name not in profiles:
            print("❌ Invalid profile selection")
            return
        
        # Confirm removal
        confirm = input(f"Are you sure you want to remove profile '{profile_name}'? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ Removal cancelled")
            return
        
        # Remove profile directory
        profile_dir = self.profiles_dir / profile_name
        if profile_dir.exists():
            shutil.rmtree(profile_dir)
        
        # Update metadata
        del metadata['profiles'][profile_name]
        if metadata['active_profile'] == profile_name:
            metadata['active_profile'] = None
        self._save_metadata(metadata)
        
        self._commit_changes(f"Remove profile: {profile_name}")
        print(f"✅ Removed profile '{profile_name}'")

    def print_status(self):
        """Print the status of the gitctx repository."""
        metadata = self._load_metadata()
        profiles = metadata['profiles']
        
        if not profiles:
            print("📝 No profiles found. Use 'gitctx add-new' or 'gitctx add-current' to create one.")
            return
        
        # Print only the active profile if it exists
        print("\n📋 Active profile:")
        active = metadata.get('active_profile')
        
        for name, info in profiles.items():
            status = "🟢 ACTIVE" if name == active else "⚪"
            profile_type = info.get('type', 'unknown')
            created = info.get('created_at', 'unknown')
            
            if name == active:
                print(f"  {status} {name} ({profile_type})")
                if 'user_name' in info:
                    print(f"    👤 {info['user_name']} <{info['user_email']}>")
                print(f"    📅 Created: {created}")
                
                # List tracked files
                files = info.get('files', {})
                if files:
                    print(f"    📁 Files: {', '.join(files.keys())}")

        # Print number of profiles
        print(f"\n📊 Total profiles: {len(profiles)}")

        # Print pending commits
        try:
            result = subprocess.run(
                ['git', 'rev-list', '--count', '@{u}..'],
                cwd=self.config_dir,
                check=True,
                capture_output=True,
                text=True
            )
            pending = int(result.stdout.strip())
            print()
            print(f"⬆️  {pending} commits pending to push")
            print()
        except subprocess.CalledProcessError as e:
            print("❌ Failed to count pending push commits")

    def list_profiles(self):
        """List all available profiles."""
        metadata = self._load_metadata()
        profiles = metadata['profiles']
        
        if not profiles:
            print("📝 No profiles found. Use 'gitctx add-new' or 'gitctx add-current' to create one.")
            return
        
        print("\n📋 Available profiles:")
        active = metadata.get('active_profile')
        
        for name, info in profiles.items():
            status = "🟢 ACTIVE" if name == active else "⚪"
            profile_type = info.get('type', 'unknown')
            created = info.get('created_at', 'unknown')
            
            print(f"  {status} {name} ({profile_type})")
            if 'user_name' in info:
                print(f"    👤 {info['user_name']} <{info['user_email']}>")
            print(f"    📅 Created: {created}")
            
            # List tracked files
            files = info.get('files', {})
            if files:
                print(f"    📁 Files: {', '.join(files.keys())}")
        print()
    
    def switch_profile(self, profile_name: str = None):
        """Switch to a different profile."""
        metadata = self._load_metadata()
        profiles = list(metadata['profiles'].keys())
        
        if not profiles:
            print("❌ No profiles found")
            return
        
        if not profile_name:
            profile_name = self._get_fzf_selection(profiles, "Select profile to activate")
        
        if not profile_name or profile_name not in profiles:
            print("❌ Invalid profile selection")
            return
        
        # Apply the profile
        profile_dir = self.profiles_dir / profile_name
        profile_info = metadata['profiles'][profile_name]
        
        # Copy all tracked files to their destination paths
        files_copied = []
        home_path = Path.home()
        
        for repo_filename, relative_path in profile_info.get('files', {}).items():
            source_file = profile_dir / repo_filename
            
            # Handle both old absolute paths and new relative paths
            if relative_path.startswith('/'):
                # Old absolute path - use as is
                dest_file = Path(relative_path)
            else:
                # New relative path - resolve from home
                dest_file = home_path / relative_path
            
            if source_file.exists():
                # Create destination directory if it doesn't exist
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file to destination
                shutil.copy2(source_file, dest_file)
                # Show original filename in output
                original_filename = repo_filename[4:] if repo_filename.startswith('dot_') else repo_filename
                files_copied.append(original_filename)
                print(f"✅ Applied {original_filename} to {dest_file}")
        
        if files_copied:
            print(f"🔧 Applied files: {', '.join(files_copied)}")
        
        # Update active profile
        metadata['active_profile'] = profile_name
        self._save_metadata(metadata)
        
        self._commit_changes(f"Switch to profile: {profile_name}")
        print(f"🔄 Switched to profile '{profile_name}'")

    # Update list_profile_files method to show relative paths properly
    def list_profile_files(self, profile_name: str = None):
        """List all files in a profile."""
        metadata = self._load_metadata()
        profiles = list(metadata['profiles'].keys())
        
        if not profiles:
            print("❌ No profiles found")
            return
        
        if not profile_name:
            profile_name = self._get_fzf_selection(profiles, "Select profile to inspect")
        
        if not profile_name or profile_name not in profiles:
            print("❌ Invalid profile selection")
            return
        
        profile_dir = self.profiles_dir / profile_name
        if not profile_dir.exists():
            print(f"❌ Profile directory not found: {profile_dir}")
            return
        
        print(f"\n📁 Files in profile '{profile_name}':")
        
        profile_info = metadata['profiles'][profile_name]
        files = profile_info.get('files', {})
        
        if not files:
            print("  (no files tracked)")
            return
        
        # Display tracked files with their paths
        home_path = Path.home()
        for repo_filename, stored_path in files.items():
            file_path = profile_dir / repo_filename
            # Show original filename in output
            display_filename = repo_filename[4:] if repo_filename.startswith('dot_') else repo_filename
            
            # Handle both old absolute paths and new relative paths
            if stored_path.startswith('/'):
                # Old absolute path
                dest_display = stored_path
            else:
                # New relative path
                dest_display = f"~/{stored_path}"
            
            if file_path.exists():
                file_size = file_path.stat().st_size
                modified = subprocess.check_output(['date', '-r', str(file_path)]).decode().strip()
                
                print(f"  📄 {display_filename}")
                print(f"    📁 Destination: {dest_display}")
                print(f"    📊 {file_size:,} bytes")
                print(f"    📅 {modified}")
                print()
            else:
                print(f"  ❌ {display_filename} (file missing)")
                print(f"    📁 Destination: {dest_display}")
                print()

    def edit_profile(self, profile_name: str = None):
        """Edit a profile's configuration."""
        metadata = self._load_metadata()
        profiles = list(metadata['profiles'].keys())
        
        if not profiles:
            print("❌ No profiles found")
            return
        
        if not profile_name:
            profile_name = self._get_fzf_selection(profiles, "Select profile to edit")
        
        if not profile_name or profile_name not in profiles:
            print("❌ Invalid profile selection")
            return
        
        profile_dir = self.profiles_dir / profile_name
        gitconfig_path = profile_dir / 'gitconfig'
        
        # Edit gitconfig
        editor = os.environ.get('EDITOR', 'vim')
        try:
            subprocess.run([editor, str(gitconfig_path)], check=True)
            self._commit_changes(f"Edit profile: {profile_name}")
            print(f"✅ Updated profile '{profile_name}'")
        except subprocess.CalledProcessError:
            print("❌ Failed to edit profile")
    
    def add_current_profile(self, profile_name: str):
        """Add current git configuration as a new profile."""
        profile_dir = self.profiles_dir / profile_name
        if profile_dir.exists():
            print(f"❌ Profile '{profile_name}' already exists")
            return
        
        # Check if global gitconfig exists
        global_gitconfig = Path.home() / '.gitconfig'
        if not global_gitconfig.exists():
            print("❌ No global .gitconfig found. Set up git first with:")
            print("    git config --global user.name 'Your Name'")
            print("    git config --global user.email 'your.email@example.com'")
            return
        
        profile_dir.mkdir()
        
        # Copy current gitconfig
        shutil.copy2(global_gitconfig, profile_dir / 'gitconfig')
        print(f"✅ Copied .gitconfig to profile '{profile_name}'")
        
        # Extract user info from gitconfig for metadata
        try:
            name_result = subprocess.run(['git', 'config', '--global', 'user.name'], 
                                    capture_output=True, text=True)
            email_result = subprocess.run(['git', 'config', '--global', 'user.email'], 
                                        capture_output=True, text=True)
            
            user_name = name_result.stdout.strip() if name_result.returncode == 0 else "Unknown"
            user_email = email_result.stdout.strip() if email_result.returncode == 0 else "Unknown"
        except Exception:
            user_name = user_email = "Unknown"
        
        # Update metadata
        metadata = self._load_metadata()
        metadata['profiles'][profile_name] = {
            'type': 'current',
            'created_at': subprocess.check_output(['date', '-Iseconds']).decode().strip(),
            'user_name': user_name,
            'user_email': user_email,
            'files': {
                'gitconfig': '.gitconfig'  # Store as relative path
            }
        }
        self._save_metadata(metadata)
        
        self._commit_changes(f"Add current profile: {profile_name}")
        print(f"✅ Added current configuration as profile '{profile_name}'")
        
        # Offer to set as active profile
        set_active = input(f"Set '{profile_name}' as the active profile? (Y/n): ").strip()
        if set_active.lower() != 'n':
            metadata['active_profile'] = profile_name
            self._save_metadata(metadata)
            self._commit_changes(f"Set active profile: {profile_name}")
            print(f"🔄 Set '{profile_name}' as active profile")

    def apply_active_profile(self):
        """Re-apply the active profile's files."""
        metadata = self._load_metadata()
        profile_name = metadata.get('active_profile')

        if not profile_name:
            print("❌ No active profile set. Use 'gitctx switch' to set one.")
            return

        profile_info = metadata['profiles'].get(profile_name)
        if not profile_info:
            print(f"❌ Profile '{profile_name}' not found in metadata")
            return

        profile_dir = self.profiles_dir / profile_name
        files = profile_info.get('files', {})
        if not files:
            print(f"❌ No files found in profile '{profile_name}'")
            return

        files_copied = []
        home_path = Path.home()

        for repo_filename, relative_path in files.items():
            source_file = profile_dir / repo_filename
            dest_file = home_path / relative_path

            if source_file.exists():
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, dest_file)
                original_filename = repo_filename[4:] if repo_filename.startswith('dot_') else repo_filename
                files_copied.append(original_filename)
                print(f"✅ Applied {original_filename} to {dest_file}")
            else:
                print(f"❌ Missing file in profile: {source_file}")

        if files_copied:
            print(f"🔁 Re-applied files: {', '.join(files_copied)}")
            self._commit_changes(f"Re-applied profile '{profile_name}'")


    def add_file(self, file_path: str, profile_name: str = None):
        """Add a file to a profile."""
        metadata = self._load_metadata()
        profiles = list(metadata['profiles'].keys())
        
        if not profiles:
            print("❌ No profiles found")
            return
        
        # Use active profile if no profile specified
        if not profile_name:
            profile_name = metadata.get('active_profile')
            if not profile_name:
                print("❌ No active profile. Set one with 'gitctx switch' or specify with --profile")
                return
        
        if profile_name not in profiles:
            print(f"❌ Profile '{profile_name}' not found")
            return
        
        # Resolve the file path
        source_path = Path(file_path).expanduser().resolve()
        if not source_path.exists():
            print(f"❌ File not found: {source_path}")
            return
        
        # Check if file is within home directory
        home_path = Path.home().resolve()
        try:
            relative_path = source_path.relative_to(home_path)
        except ValueError:
            print(f"❌ File must be within home directory for portability")
            print(f"   File: {source_path}")
            print(f"   Home: {home_path}")
            return
        
        # Copy file to profile directory
        profile_dir = self.profiles_dir / profile_name
        original_filename = source_path.name
        # Convert dotfiles to visible names in repo
        repo_filename = f"dot_{original_filename[1:]}" if original_filename.startswith('.') else original_filename
        dest_file = profile_dir / repo_filename

        # Update metadata to track this file with relative path
        profile_info = metadata['profiles'][profile_name]
        if 'files' not in profile_info:
            profile_info['files'] = {}

        # Check if this file (by relative path) already exists in profile
        relative_path_str = str(relative_path)
        existing_repo_filename = None
        
        for existing_repo_file, existing_relative_path in profile_info['files'].items():
            if existing_relative_path == relative_path_str:
                existing_repo_filename = existing_repo_file
                break
        
        action = "Updated"
        if existing_repo_filename:
            # File already exists, remove old entry and update
            old_file = profile_dir / existing_repo_filename
            if old_file.exists() and existing_repo_filename != repo_filename:
                old_file.unlink()  # Remove old file if filename changed
            del profile_info['files'][existing_repo_filename]
        else:
            action = "Added"

        # Copy the file
        shutil.copy2(source_path, dest_file)

        # Store with new repo filename
        profile_info['files'][repo_filename] = relative_path_str
        self._save_metadata(metadata)

        self._commit_changes(f"{action} file {original_filename} to profile {profile_name}")
        print(f"✅ {action} '{original_filename}' to profile '{profile_name}'")
        print(f"📁 File path: ~/{relative_path}")

    def edit_file(self, file: Optional[str] = None, profile_name: Optional[str] = None):
        """Edit a file in a profile using $EDITOR (defaults to vim)."""
        metadata = self._load_metadata()
        profiles = metadata.get('profiles', {})

        if not profiles:
            print("❌ No profiles found")
            return

        profile_name = profile_name or metadata.get('active_profile')
        if not profile_name or profile_name not in profiles:
            print("❌ Invalid or missing profile")
            return

        profile_info = profiles[profile_name]
        files = profile_info.get('files', {})

        if not files:
            print(f"❌ Profile '{profile_name}' has no files")
            return

        if not file:
            file = self._get_fzf_selection(list(files.keys()), f"Select file to edit in '{profile_name}'")

        if not file or file not in files:
            print("❌ Invalid file selection")
            return

        file_path = self.profiles_dir / profile_name / file
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            return

        editor = os.environ.get('EDITOR', 'vim')
        try:
            subprocess.run([editor, str(file_path)], check=True)
            self._commit_changes(f"Edit file '{file}' in profile '{profile_name}'")
            print(f"✅ Edited '{file}' in '{profile_name}'")
        except subprocess.CalledProcessError:
            print(f"❌ Failed to edit '{file}'")

    def remove_file(self, file: Optional[str] = None, profile_name: Optional[str] = None):
        metadata = self._load_metadata()
        profiles = metadata.get('profiles', {})
        
        if not profiles:
            print("❌ No profiles found")
            return

        profile_name = profile_name or metadata.get('active_profile')
        if not profile_name or profile_name not in profiles:
            print("❌ Invalid or missing profile")
            return
        
        profile_info = profiles[profile_name]
        files = profile_info.get('files', {})

        if not files:
            print(f"❌ Profile '{profile_name}' has no files")
            return

        if not file:
            file = self._get_fzf_selection(list(files.keys()), f"Select file to remove from '{profile_name}'")
        
        if not file or file not in files:
            print("❌ Invalid file selection")
            return

        # Remove the file from profile dir
        profile_dir = self.profiles_dir / profile_name
        file_path = profile_dir / file
        if file_path.exists():
            file_path.unlink()

        del files[file]
        self._save_metadata(metadata)
        self._commit_changes(f"Removed file '{file}' from profile '{profile_name}'")
        print(f"🗑️ Removed '{file}' from '{profile_name}'")

    def push_repo(self):
        try:
            subprocess.run(['git', 'push'], cwd=self.config_dir, check=True)
            print("🚀 Pushed changes to remote")
        except subprocess.CalledProcessError:
            print("❌ Failed to push changes")

    def pull_repo(self):
        try:
            subprocess.run(['git', 'pull'], cwd=self.config_dir, check=True)
            print("📥 Pulled latest changes from remote")
        except subprocess.CalledProcessError:
            print("❌ Failed to pull changes")

def main():
    parser = argparse.ArgumentParser(description='gitctx - Git Profile Manager')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Initialize command
    init_parser = subparsers.add_parser('init', help='Initialize gitctx repository (alias)')
    init_parser.add_argument('repo_url', nargs='?', help='Optional repository URL to clone')
    
    # Switch profile
    switch_parser = subparsers.add_parser('switch', help='Switch to a profile (alias)')
    switch_parser.add_argument('name', nargs='?', help='Profile name (optional, will prompt if not provided)')

    # Status
    status_parser = subparsers.add_parser('status', help='List all profiles (alias)')

    # Profile management commands
    profile_parser = subparsers.add_parser('profile', help='Grouped profile management commands')
    profile_subparsers = profile_parser.add_subparsers(dest='profile_command', help='Profile commands')
    
    # Add new profile
    add_new = profile_subparsers.add_parser('add-new', help='Create new git profile')
    add_new.add_argument('name', help='Profile name')
    add_new.add_argument('--user-name', required=True, help='Git user name')
    add_new.add_argument('--user-email', required=True, help='Git user email')
    
    # Add current profile
    add_current = profile_subparsers.add_parser('add-current', help='Add current git configuration as a profile')
    add_current.add_argument('name', help='Profile name')

    # List profiles
    profile_subparsers.add_parser('list', help='List all profiles')

    
    # Switch profile
    switch = profile_subparsers.add_parser('switch', help='Switch to a profile')
    switch.add_argument('name', nargs='?', help='Profile name (optional, will prompt if not provided)')
    
    # List profile files
    inspect = profile_subparsers.add_parser('inspect', help='List all files in a profile')
    inspect.add_argument('name', nargs='?', help='Profile name (optional, will prompt if not provided)')
    
    # Edit profile
    edit = profile_subparsers.add_parser('edit', help='Edit a profile')
    edit.add_argument('name', nargs='?', help='Profile name (optional, will prompt if not provided)')
    
    # Remove profile
    remove = profile_subparsers.add_parser('rm', help='Remove git profile')
    remove.add_argument('name', nargs='?', help='Profile name (optional, will prompt if not provided)')
    
    # File management commands
    file_parser = subparsers.add_parser('file', help='Grouped file management commands')
    file_subparsers = file_parser.add_subparsers(dest='file_command', help='File commands')
    
    # Add file to profile
    add_file = file_subparsers.add_parser('add', help='Add a file to a profile')
    add_file.add_argument('file', help='Path to file to add')
    add_file.add_argument('--profile', help='Profile name (defaults to active profile)')

    # Edit file in profile
    edit_file = file_subparsers.add_parser('edit', help='Edit a file in a profile')
    edit_file.add_argument('file', nargs='?', help='File name to edit (optional, fzf prompt if omitted)')
    edit_file.add_argument('--profile', help='Profile name (defaults to active profile)')

    # Remove file from profile
    rm_file = file_subparsers.add_parser('rm', help='Remove file from profile')
    rm_file.add_argument('file', nargs='?', help='File name to remove (optional, fzf prompt if omitted)')
    rm_file.add_argument('--profile', help='Profile name (defaults to active profile)')

    # Config/git repository commands
    config_parser = subparsers.add_parser('config', help='Grouped cn¡onfiguration management commands')
    config_subparsers = config_parser.add_subparsers(dest='config_command', help='Config commands')
    
    # Init config
    init_config = config_subparsers.add_parser('init', help='Initialize gitctx repository')
    init_config.add_argument('repo_url', nargs='?', help='Optional repository URL to clone')

    # Push and pull from git
    config_subparsers.add_parser('push', help='Push changes in gitctx repository')
    config_subparsers.add_parser('pull', help='Pull latest changes in gitctx repository')
    
    # Apply profile configuration
    config_subparsers.add_parser('apply', help='Re-apply files from the current active profile')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    gitctx = GitCtx()
    
    try:
        if args.command == 'init':
            gitctx.initialize_repo(getattr(args, 'repo_url', None))
        elif args.command == 'profile':
            if not args.profile_command:
                profile_parser.print_help()
                return
            if args.profile_command == 'add-new':
                gitctx.add_new_profile(args.name, args.user_name, args.user_email)
            elif args.profile_command == 'add-current':
                gitctx.add_current_profile(args.name)
            elif args.profile_command == 'edit':
                gitctx.edit_profile(args.name)
            elif args.profile_command == 'rm':
                gitctx.remove_profile(args.name)
            elif args.profile_command == 'list':
                gitctx.list_profiles()
            elif args.profile_command == 'inspect':
                gitctx.list_profile_files(args.name)
            elif args.profile_command == 'switch':
                gitctx.switch_profile(args.name)
        elif args.command == 'status':
            gitctx.print_status()
        elif args.command == 'switch':
            gitctx.switch_profile(args.name)
        elif args.command == 'file':
            if not args.file_command:
                file_parser.print_help()
                return
            if args.file_command == 'add':
                gitctx.add_file(args.file, args.profile)
            elif args.file_command == 'edit':
                gitctx.edit_file(args.file, args.profile)
            elif args.file_command == 'rm':
                gitctx.remove_file(args.file, args.profile)
        elif args.command == 'config':
            if not args.config_command:
                config_parser.print_help()
                return
            if args.config_command == 'init':
                gitctx.initialize_repo(getattr(args, 'repo_url', None))
            if args.config_command == 'push':
                gitctx.push_repo()
            elif args.config_command == 'pull':
                gitctx.pull_repo()
            elif args.config_command == 'apply':
                gitctx.apply_active_profile()
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
