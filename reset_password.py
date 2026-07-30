"""Reset the local development admin password without printing secrets."""

import getpass
import os
import subprocess
import sys

from auth_utils import hash_password


def _sql_quote(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _read_secret(name: str, prompt: str) -> str:
    value = os.environ.get(name)
    if value:
        return value
    return getpass.getpass(prompt)


def reset_admin_password() -> int:
    admin_username = os.environ.get("RESET_ADMIN_USERNAME", "admin")
    mysql_container = os.environ.get("RESET_MYSQL_CONTAINER", "lemon_kami_mysql")
    mysql_database = os.environ.get("RESET_MYSQL_DATABASE", "lemon_kami")
    mysql_user = os.environ.get("RESET_MYSQL_USER", "root")
    mysql_password = _read_secret("RESET_MYSQL_PASSWORD", "MySQL password: ")
    new_password = _read_secret("RESET_ADMIN_PASSWORD", "New admin password: ")

    if not mysql_password or not new_password:
        print("Missing required password input.", file=sys.stderr)
        return 1

    password_hash = hash_password(new_password)
    sql = (
        "UPDATE admin_users SET "
        f"password_hash={_sql_quote(password_hash)} "
        f"WHERE username={_sql_quote(admin_username)};"
    )
    cmd = [
        "docker",
        "exec",
        "-i",
        "-e",
        "MYSQL_PWD",
        mysql_container,
        "mysql",
        "-u",
        mysql_user,
        mysql_database,
    ]
    env = os.environ.copy()
    env["MYSQL_PWD"] = mysql_password

    try:
        subprocess.run(
            cmd,
            input=f"{sql}\n",
            env=env,
            text=True,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as error:
        print("Failed to reset admin password. Check Docker/MySQL status.", file=sys.stderr)
        if error.stderr:
            print(error.stderr.strip(), file=sys.stderr)
        return error.returncode or 1
    except FileNotFoundError:
        print("Docker command was not found.", file=sys.stderr)
        return 1

    print(f"Admin password reset for user {admin_username}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(reset_admin_password())
