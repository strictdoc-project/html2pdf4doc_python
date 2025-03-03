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

echo "html2print/docker: running a Docker container entrypoint."
echo "html2print/docker: ensuring html2print user with UID=$HOST_UID and GID=$HOST_GID exists"

# Check if a user with this UID already exists (e.g., "ubuntu")
EXISTING_USER=$(getent passwd "$HOST_UID" | cut -d: -f1)

if [ -n "$EXISTING_USER" ]; then
    echo "error: html2print/docker: detected a wrong user: '$EXISTING_USER'. Ensure that any default users are removed from the Dockerfile. This entrypoint script is supposed to create a new user 'html2print'."
    exit 1
else
    # Ensure the group exists.
    EXISTING_GROUP=$(getent group "$HOST_GID" | cut -d: -f1)
    if [ -z "$EXISTING_GROUP" ]; then
        echo "html2print/docker: creating new group html2print with GID=$HOST_GID"
        groupadd -g "$HOST_GID" html2print
    else
        echo "html2print/docker: group with GID=$HOST_GID already exists: $EXISTING_GROUP, reusing it."
    fi

    # Create the user.
    echo "html2print/docker: creating new user html2print with UID=$HOST_UID"
    useradd -m -u "$HOST_UID" -g "$HOST_GID" -s /bin/bash html2print

    # Give the user root privileges. Useful for debugging.
    echo "html2print ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/html2print
fi

echo "html2print/docker: show created user info:"
id html2print

# Run as the correct user. If no command is provided, run a shell.
if [ $# -eq 0 ]; then
    echo "html2print/docker: no command provided, opening an interactive shell."
    exec gosu html2print /bin/bash
else
    # Otherwise, run the provided command.
    exec gosu html2print "$@"
fi
