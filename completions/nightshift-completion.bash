#!/usr/bin/env bash
# Bash completion script for nightshift
# Generated for Click 8.0+ command-line interface
#
# Installation:
#   Source this file in your ~/.bashrc or copy to /etc/bash_completion.d/
#
#   # Add to ~/.bashrc:
#   source /path/to/nightshift-completion.bash
#
#   # Or copy to system directory:
#   sudo cp nightshift-completion.bash /etc/bash_completion.d/nightshift

_nightshift_completion() {
    local IFS=$'\n'
    local response

    response=$(env COMP_WORDS="${COMP_WORDS[*]}" COMP_CWORD=$COMP_CWORD _NIGHTSHIFT_COMPLETE=bash_complete $1)

    for completion in $response; do
        IFS=',' read type value <<< "$completion"

        if [[ $type == 'dir' ]]; then
            COMPREPLY=()
            compopt -o dirnames
        elif [[ $type == 'file' ]]; then
            COMPREPLY=()
            compopt -o default
        elif [[ $type == 'plain' ]]; then
            COMPREPLY+=($value)
        fi
    done

    return 0
}

_nightshift_completion_setup() {
    complete -o nosort -F _nightshift_completion nightshift
}

_nightshift_completion_setup
