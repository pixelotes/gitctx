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
import tempfile

class GitCtx:
    def __init__(self):
        self.config_dir = Path.home() / '.config' / 'gitctx'
        self.profiles_dir = self.config_dir / 'profiles'
        self.repo_dir = self.config_dir
        self.metadata_file = self.config_dir / 'metadata.json'
        
    def initialize_repo(self):
        """Initialize the gitctx configuration repository."""
        if not self.config_dir.exists():
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
        else:
            print(f"✅ gitctx repository already exists at {self.config_dir}")
    
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
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout, _ = process.communicate('\n'.join(options))
                if process.returncode == 0:
                    return stdout.strip()
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
                'gitconfig': str(Path.home() / '.gitconfig')
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
        for filename, dest_path in profile_info.get('files', {}).items():
            source_file = profile_dir / filename
            dest_file = Path(dest_path)
            
            if source_file.exists():
                # Create destination directory if it doesn't exist
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file to destination
                shutil.copy2(source_file, dest_file)
                files_copied.append(filename)
                print(f"✅ Applied {filename} to {dest_path}")
        
        if files_copied:
            print(f"🔧 Applied files: {', '.join(files_copied)}")
        
        # Update active profile
        metadata['active_profile'] = profile_name
        self._save_metadata(metadata)
        
        self._commit_changes(f"Switch to profile: {profile_name}")
        print(f"🔄 Switched to profile '{profile_name}'")
    
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
        for filename, dest_path in files.items():
            file_path = profile_dir / filename
            
            if file_path.exists():
                file_size = file_path.stat().st_size
                modified = subprocess.check_output(['date', '-r', str(file_path)]).decode().strip()
                
                print(f"  📄 {filename}")
                print(f"    📁 Destination: {dest_path}")
                print(f"    📊 {file_size:,} bytes")
                print(f"    📅 {modified}")
                print()
            else:
                print(f"  ❌ {filename} (file missing)")
                print(f"    📁 Destination: {dest_path}")
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
                'gitconfig': str(global_gitconfig)
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

    def cd_to_config(self):
        """Print the path to the gitctx config directory for cd command."""
        print(str(self.config_dir))
        os.chdir(self.config_dir)

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
        
        # Copy file to profile directory
        profile_dir = self.profiles_dir / profile_name
        filename = source_path.name
        dest_file = profile_dir / filename
        
        shutil.copy2(source_path, dest_file)
        
        # Update metadata to track this file
        profile_info = metadata['profiles'][profile_name]
        if 'files' not in profile_info:
            profile_info['files'] = {}
        
        profile_info['files'][filename] = str(source_path)
        self._save_metadata(metadata)
        
        self._commit_changes(f"Add file {filename} to profile {profile_name}")
        print(f"✅ Added '{filename}' to profile '{profile_name}'")
        print(f"📁 File will be copied to: {source_path}")

def main():
    parser = argparse.ArgumentParser(description='gitctx - Git Profile Manager')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Initialize command
    subparsers.add_parser('init', help='Initialize gitctx repository')
    
    # Add new profile
    add_new = subparsers.add_parser('add-new', help='Create new git profile')
    add_new.add_argument('name', help='Profile name')
    add_new.add_argument('--user-name', required=True, help='Git user name')
    add_new.add_argument('--user-email', required=True, help='Git user email')
    
    # Add current profile
    add_current = subparsers.add_parser('add-current', help='Add current git configuration as a profile')
    add_current.add_argument('name', help='Profile name')
    
    # Remove profile
    remove = subparsers.add_parser('remove', help='Remove git profile')
    remove.add_argument('name', nargs='?', help='Profile name (optional, will prompt if not provided)')
    
    # List profiles
    subparsers.add_parser('list', help='List all profiles')
    
    # Switch profile
    switch = subparsers.add_parser('switch', help='Switch to a profile')
    switch.add_argument('name', nargs='?', help='Profile name (optional, will prompt if not provided)')
    
    # Edit profile
    edit = subparsers.add_parser('edit', help='Edit a profile')
    edit.add_argument('name', nargs='?', help='Profile name (optional, will prompt if not provided)')
    
    # List profile files
    inspect = subparsers.add_parser('inspect', help='List all files in a profile')
    inspect.add_argument('name', nargs='?', help='Profile name (optional, will prompt if not provided)')
    
    # CD to config directory
    subparsers.add_parser('cd', help='Print path to gitctx config directory')
    
    # Add file to profile
    add_file = subparsers.add_parser('add', help='Add a file to a profile')
    add_file.add_argument('file', help='Path to file to add')
    add_file.add_argument('--profile', help='Profile name (defaults to active profile)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    gitctx = GitCtx()
    
    try:
        if args.command == 'init':
            gitctx.initialize_repo()
        elif args.command == 'add-new':
            gitctx.add_new_profile(args.name, args.user_name, args.user_email)
        elif args.command == 'add-current':
            gitctx.add_current_profile(args.name)
        elif args.command == 'remove':
            gitctx.remove_profile(args.name)
        elif args.command == 'list':
            gitctx.list_profiles()
        elif args.command == 'switch':
            gitctx.switch_profile(args.name)
        elif args.command == 'edit':
            gitctx.edit_profile(args.name)
        elif args.command == 'inspect':
            gitctx.list_profile_files(args.name)
        elif args.command == 'cd':
            gitctx.cd_to_config()
        elif args.command == 'add':
            gitctx.add_file(args.file, args.profile)
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
