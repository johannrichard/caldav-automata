#!/bin/sh
# CalDAV Automata entrypoint — thin wrapper around the Python daemon.
# Using CMD in the Dockerfile is preferred; this script exists for
# container runtimes that require a shell entry point.
exec python -m caldav_automata.main "$@"
