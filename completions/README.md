# NightShift Shell Completion

This directory contains shell completion scripts for the `nightshift` command-line interface. Autocompletion enables tab-completion for commands, options, and arguments, making it faster and easier to use NightShift.

## Features

- **Command completion**: Tab-complete all nightshift commands (`submit`, `queue`, `approve`, `results`, `cancel`, `clear`)
- **Option completion**: Tab-complete command options and flags (e.g., `--auto-approve`, `--status`, `--show-output`, `--confirm`)
- **Dynamic completion**: Context-aware completion for command arguments
- **Help text**: View command descriptions while completing (zsh only)

## Supported Shells

- Bash 4.4+
- Zsh 5.0+

## Installation

### Bash

#### Option 1: User Installation (Recommended)

Add the following line to your `~/.bashrc`:

```bash
eval "$(_NIGHTSHIFT_COMPLETE=bash_source nightshift)"
```

Then reload your shell:

```bash
source ~/.bashrc
```

#### Option 2: Manual Installation

1. Copy the completion script to a location in your home directory:
   ```bash
   mkdir -p ~/.local/share/bash-completion/completions
   cp completions/nightshift-completion.bash ~/.local/share/bash-completion/completions/nightshift
   ```

2. Source it in your `~/.bashrc`:
   ```bash
   source ~/.local/share/bash-completion/completions/nightshift
   ```

#### Option 3: System-wide Installation

For system-wide installation (requires root):

```bash
sudo cp completions/nightshift-completion.bash /etc/bash_completion.d/nightshift
```

### Zsh

#### Option 1: User Installation (Recommended)

Add the following lines to your `~/.zshrc` (before any `compinit` call):

```zsh
eval "$(_NIGHTSHIFT_COMPLETE=zsh_source nightshift)"
```

Then reload your shell:

```zsh
source ~/.zshrc
```

#### Option 2: Manual Installation with fpath

1. Create a completions directory and copy the script:
   ```zsh
   mkdir -p ~/.zsh/completions
   cp completions/nightshift-completion.zsh ~/.zsh/completions/_nightshift
   ```

2. Add the completions directory to your `fpath` in `~/.zshrc` (before `compinit`):
   ```zsh
   fpath=(~/.zsh/completions $fpath)
   autoload -Uz compinit && compinit
   ```

3. Reload your shell:
   ```zsh
   source ~/.zshrc
   ```

#### Option 3: System-wide Installation

For system-wide installation (requires root):

```zsh
sudo cp completions/nightshift-completion.zsh /usr/local/share/zsh/site-functions/_nightshift
```

## Usage Examples

Once installed, you can use tab completion with the `nightshift` command:

### Command Completion

```bash
nightshift <TAB>
# Shows: submit queue approve results cancel clear
```

### Option Completion

```bash
nightshift submit --<TAB>
# Shows: --auto-approve --help

nightshift queue --<TAB>
# Shows: --status --help

nightshift results --<TAB>
# Shows: --show-output --help

nightshift clear --<TAB>
# Shows: --confirm --help
```

### Status Value Completion

```bash
nightshift queue --status <TAB>
# Shows: staged committed running completed failed cancelled
```

### Command Help

```bash
nightshift submit --help
nightshift queue --help
nightshift approve --help
nightshift results --help
nightshift cancel --help
nightshift clear --help
```

## Troubleshooting

### Completion Not Working

1. **Verify nightshift is installed and in PATH**:
   ```bash
   which nightshift
   nightshift --help
   ```

2. **Check your shell**:
   ```bash
   echo $SHELL
   ```

3. **For Bash**: Ensure bash-completion is installed:
   ```bash
   # macOS
   brew install bash-completion@2

   # Ubuntu/Debian
   sudo apt-get install bash-completion

   # RHEL/CentOS/Fedora
   sudo yum install bash-completion
   ```

4. **For Zsh**: Ensure compinit is called in your `.zshrc`:
   ```zsh
   autoload -Uz compinit && compinit
   ```

5. **Reload your shell**:
   ```bash
   # Bash
   source ~/.bashrc

   # Zsh
   source ~/.zshrc
   ```

6. **Clear completion cache (Zsh only)**:
   ```zsh
   rm -f ~/.zcompdump*
   compinit
   ```

### Completion Shows Raw Variables

If you see environment variable names like `_NIGHTSHIFT_COMPLETE` instead of completions, the Click library may not be installed correctly:

```bash
pip install --upgrade click>=8.0.0
```

### Completion Is Slow

If completions are slow, especially for dynamic completions, this is normal as Click queries the application for valid completions. You can disable dynamic completions if needed.

## Technical Details

NightShift uses [Click's shell completion](https://click.palletsprojects.com/en/8.1.x/shell-completion/) feature, which leverages the Click framework's built-in completion support. The completion scripts work by:

1. Setting the `_NIGHTSHIFT_COMPLETE` environment variable
2. Running the `nightshift` command with special completion mode enabled
3. Parsing the output to provide context-aware suggestions

### Click Version Requirements

- Click 8.0.0 or higher is required for full completion support
- NightShift requires Click 8.1.0+ as specified in `setup.py`

### Completion Types

The scripts support three types of completions:

- **plain**: Regular text completions (commands, options, status values)
- **file**: File path completions
- **dir**: Directory path completions

## Contributing

If you find issues with the completion scripts or have suggestions for improvements, please open an issue or submit a pull request on the [NightShift GitHub repository](https://github.com/james-alvey-42/nightshift).

## License

These completion scripts are part of the NightShift project and are distributed under the same license as the main project.
