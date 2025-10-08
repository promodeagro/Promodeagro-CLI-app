#!/usr/bin/env python3
"""
Admin helper to set a bcrypt password for a user in dev-promodeagro-admin-promodeagroUsers

Usage:
  python3 ddb_set_password.py EMAIL PASSWORD

Requires: boto3, bcrypt
"""
import sys
from typing import Any, Dict

def ensure_deps() -> None:
    missing = []
    try:
        import boto3  # noqa: F401
    except Exception:
        missing.append("boto3")
    try:
        import bcrypt  # noqa: F401
    except Exception:
        missing.append("bcrypt")
    if missing:
        sys.stderr.write("Missing: %s\nInstall: pip install %s\n" % (", ".join(missing), " ".join(missing)))
        sys.exit(1)

ensure_deps()

import boto3
import bcrypt

USERS_TABLE = "dev-promodeagro-admin-promodeagroUsers"


def find_user_by_email(ddb, email: str) -> Dict[str, Any]:
    resp = ddb.query(
        TableName=USERS_TABLE,
        IndexName="emailIndex",
        KeyConditionExpression="#e = :email",
        ExpressionAttributeNames={"#e": "email"},
        ExpressionAttributeValues={":email": {"S": email}},
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else {}


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python3 ddb_set_password.py EMAIL PASSWORD")
        sys.exit(1)
    email = sys.argv[1]
    password = sys.argv[2]
    ddb = boto3.client("dynamodb", region_name="ap-south-1")
    user = find_user_by_email(ddb, email)
    if not user:
        print("User not found for email:", email)
        sys.exit(2)
    # Need user's primary key id to update
    from boto3.dynamodb.types import TypeDeserializer
    deser = TypeDeserializer()
    user_id = deser.deserialize(user.get("id")) if user.get("id") else None
    if not user_id:
        print("User item missing 'id' attribute; cannot set password.")
        sys.exit(3)
    phash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    ddb.update_item(
        TableName=USERS_TABLE,
        Key={"id": {"S": str(user_id)}},
        UpdateExpression="SET #ph = :ph",
        ExpressionAttributeNames={"#ph": "passwordHash"},
        ExpressionAttributeValues={":ph": {"S": phash}},
    )
    print("Password set for:", email)


if __name__ == "__main__":
    main()


