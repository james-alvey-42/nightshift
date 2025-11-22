#!/usr/bin/env zsh
# Zsh completion script for nightshift
# Generated for Click 8.0+ command-line interface
#
# Installation:
#   Place this file in a directory in your $fpath (e.g., ~/.zsh/completions/)
#   and ensure it's named _nightshift (note the underscore prefix)
#
#   # Add to ~/.zshrc:
#   fpath=(~/.zsh/completions $fpath)
#   autoload -Uz compinit && compinit
#
#   # Then copy this file:
#   mkdir -p ~/.zsh/completions
#   cp nightshift-completion.zsh ~/.zsh/completions/_nightshift

#compdef nightshift

_nightshift_completion() {
    local -a completions
    local -a completions_with_descriptions
    local -a response
    (( ! $+commands[nightshift] )) && return 1

    response=("${(@f)$(env COMP_WORDS="${words[*]}" COMP_CWORD=$((CURRENT-1)) _NIGHTSHIFT_COMPLETE=zsh_complete nightshift)}")

    for type key descr in ${response}; do
        if [[ "$type" == "plain" ]]; then
            if [[ "$descr" == "_" ]]; then
                completions+=("$key")
            else
                completions_with_descriptions+=("$key":"$descr")
            fi
        elif [[ "$type" == "dir" ]]; then
            _path_files -/
        elif [[ "$type" == "file" ]]; then
            _path_files -f
        fi
    done

    if [ -n "$completions_with_descriptions" ]; then
        _describe -V unsorted completions_with_descriptions -U
    fi

    if [ -n "$completions" ]; then
        compadd -U -V unsorted -a completions
    fi
}

if [[ $zsh_eval_context[-1] == loadautofunc ]]; then
    # autoload from fpath, call function directly
    _nightshift_completion "$@"
else
    # eval/source/. command, register function for later
    compdef _nightshift_completion nightshift
fi
