#!/bin/sh

# This custom entrypoint script is needed for creating a container user with
# a host's UID/GUI which enables sharing of the files between the container
# and the host.
# NOTE: It is important that a non-root user is used because otherwise the
# Chrome Driver fails with: "User data directory is already in use"
# https://github.com/SeleniumHQ/selenium/issues/15327#issuecomment-2688613182

set -e

# Ensure we have the environment variables
if [ -z "$HOST_UID" ] || [ -z "$HOST_GID" ]; then
    echo "HOST_UID and HOST_GID must be set!"
    exit 1
fi

echo "html2pdf4doc/docker: running a Docker container entrypoint."
echo "html2pdf4doc/docker: ensuring html2pdf4doc user with UID=$HOST_UID and GID=$HOST_GID exists"

# Check if a user with this UID already exists (e.g., "ubuntu")
EXISTING_USER=$(getent passwd "$HOST_UID" | cut -d: -f1)

if [ -n "$EXISTING_USER" ]; then
    echo "error: html2pdf4doc/docker: detected a wrong user: '$EXISTING_USER'. Ensure that any default users are removed from the Dockerfile. This entrypoint script is supposed to create a new user 'html2pdf4doc'."
    exit 1
else
    # Ensure the group exists.
    EXISTING_GROUP=$(getent group "$HOST_GID" | cut -d: -f1)
    if [ -z "$EXISTING_GROUP" ]; then
        echo "html2pdf4doc/docker: creating new group html2pdf4doc with GID=$HOST_GID"
        groupadd -g "$HOST_GID" html2pdf4doc
    else
        echo "html2pdf4doc/docker: group with GID=$HOST_GID already exists: $EXISTING_GROUP, reusing it."
    fi

    # Create the user.
    echo "html2pdf4doc/docker: creating new user html2pdf4doc with UID=$HOST_UID"
    useradd -m -u "$HOST_UID" -g "$HOST_GID" -s /bin/bash html2pdf4doc

    # Give the user root privileges. Useful for debugging.
    echo "html2pdf4doc ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/html2pdf4doc
fi

echo "html2pdf4doc/docker: show created user info:"
id html2pdf4doc

# Run as the correct user. If no command is provided, run a shell.
if [ $# -eq 0 ]; then
    echo "html2pdf4doc/docker: no command provided, opening an interactive shell."
    exec gosu html2pdf4doc /bin/bash
else
    # Otherwise, run the provided command.
    exec gosu html2pdf4doc "$@"
fi
