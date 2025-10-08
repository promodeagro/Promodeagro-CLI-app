#!/usr/bin/env python3
"""
Menu-driven CLI using DynamoDB backend, organized by an OpenAPI YAML structure.

- Uses boto3 to operate directly on dev DynamoDB tables
- Uses rich for a colorized UI
- Parses the provided OpenAPI YAML only to group menus (Auth, Orders, Profile, Notifications, System)
"""
import sys
import json
from typing import Any, Dict, List, Optional
from decimal import Decimal


def _ensure_deps() -> None:
    missing: List[str] = []
    try:
        import boto3  # noqa: F401
        from boto3.dynamodb.types import TypeDeserializer  # noqa: F401
    except Exception:
        missing.append("boto3")
    try:
        import yaml  # noqa: F401
    except Exception:
        missing.append("pyyaml")
    try:
        from rich import print  # noqa: F401
        from rich.console import Console  # noqa: F401
        from rich.panel import Panel  # noqa: F401
        from rich.table import Table  # noqa: F401
        from rich.prompt import Prompt, IntPrompt, Confirm  # noqa: F401
        from rich.json import JSON as RichJSON  # noqa: F401
    except Exception:
        missing.append("rich")
    try:
        import bcrypt  # noqa: F401
    except Exception:
        missing.append("bcrypt")
    if missing:
        sys.stderr.write("Missing: %s\nInstall: pip install %s\n" % (", ".join(missing), " ".join(missing)))
        sys.exit(1)


_ensure_deps()

import boto3
from boto3.dynamodb.types import TypeDeserializer
import yaml
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.json import JSON as RichJSON
import bcrypt


OPENAPI_YAML = """
openapi: 3.0.0
info:
  title: Promodeagro Packer API
  version: 1.0.0
  description: Unified API specification for Auth, Orders, Profile, and Notifications
servers:
  - url: http://localhost:3000
paths: {}
components: {}
"""


console = Console()


def _to_jsonable(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        # Convert to int if whole number, else float
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_jsonable(v) for v in obj]
    return obj


def print_json(data: Any) -> None:
    console.print(RichJSON.from_data(_to_jsonable(data)))


class DDB:
    def __init__(self, region: str = "ap-south-1") -> None:
        self.ddb = boto3.client("dynamodb", region_name=region)
        self.deserializer = TypeDeserializer()
        # Tables
        self.orders = "dev-promodeagro-admin-OrdersTable"
        self.packers = "dev-promodeagro-admin-PackersTable"
        self.users = "dev-promodeagro-admin-promodeagroUsers"
        self.notifications = "dev-promodeagro-admin-notificationsTable"

    def _unmarshal(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {k: self.deserializer.deserialize(v) for k, v in item.items()}

    # Auth (simplified): login by email (fetch user), forgot/reset placeholders
    def login_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        try:
            resp = self.ddb.query(
                TableName=self.users,
                IndexName="emailIndex",
                KeyConditionExpression="#e = :email",
                ExpressionAttributeNames={"#e": "email"},
                ExpressionAttributeValues={":email": {"S": email}},
                Limit=1,
            )
            items = resp.get("Items", [])
            return self._unmarshal(items[0]) if items else None
        except self.ddb.exceptions.ResourceNotFoundException:
            return None

    def login_with_password(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        user = self.login_by_email(email)
        if not user:
            return None
        # Support both camelCase and snake_case
        password_hash = user.get("passwordHash") or user.get("password_hash")
        if not password_hash or not isinstance(password_hash, str):
            return None
        try:
            ok = bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except Exception:
            ok = False
        return user if ok else None

    # Orders
    def list_orders_by_status(self, status: str, limit: int = 50) -> List[Dict[str, Any]]:
        resp = self.ddb.query(
            TableName=self.orders,
            IndexName="statusCreatedAtIndex",
            KeyConditionExpression="#s = :status",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":status": {"S": status}},
            ScanIndexForward=False,
            Limit=limit,
        )
        return [self._unmarshal(i) for i in resp.get("Items", [])]

    def query_orders_page(self, status: str, limit: int = 20, eks: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "TableName": self.orders,
            "IndexName": "statusCreatedAtIndex",
            "KeyConditionExpression": "#s = :status",
            "ExpressionAttributeNames": {"#s": "status"},
            "ExpressionAttributeValues": {":status": {"S": status}},
            "ScanIndexForward": False,
            "Limit": limit,
        }
        if eks:
            kwargs["ExclusiveStartKey"] = eks
        resp = self.ddb.query(**kwargs)
        items = [self._unmarshal(i) for i in resp.get("Items", [])]
        return {"items": items, "last_key": resp.get("LastEvaluatedKey")}

    def list_all_orders_by_status(self, status: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        eks = None
        while True:
            kwargs = {
                "TableName": self.orders,
                "IndexName": "statusCreatedAtIndex",
                "KeyConditionExpression": "#s = :status",
                "ExpressionAttributeNames": {"#s": "status"},
                "ExpressionAttributeValues": {":status": {"S": status}},
                "ScanIndexForward": False,
            }
            if eks:
                kwargs["ExclusiveStartKey"] = eks
            resp = self.ddb.query(**kwargs)
            items.extend([self._unmarshal(i) for i in resp.get("Items", [])])
            eks = resp.get("LastEvaluatedKey")
            if not eks:
                break
        return items

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        resp = self.ddb.get_item(TableName=self.orders, Key={"id": {"S": order_id}})
        item = resp.get("Item")
        return self._unmarshal(item) if item else None

    def count_orders_by_status(self, status: str) -> int:
        resp = self.ddb.query(
            TableName=self.orders,
            IndexName="statusCreatedAtIndex",
            KeyConditionExpression="#s = :status",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":status": {"S": status}},
            Select="COUNT",
        )
        return int(resp.get("Count", 0))

    def complete_all_unpacked(self, packed_by: str, photo_url: str, video_url: str, max_items: int = 100) -> Dict[str, Any]:
        # Fetch first N unpacked orders and mark all as packed
        resp = self.ddb.query(
            TableName=self.orders,
            IndexName="statusCreatedAtIndex",
            KeyConditionExpression="#s = :status",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":status": {"S": "unpacked"}},
            ScanIndexForward=False,
            Limit=max_items,
        )
        items = resp.get("Items", [])
        ids = [i.get("id", {}).get("S") for i in items if i.get("id", {}).get("S")]
        updated: List[str] = []
        errors: List[str] = []
        for oid in ids:
            try:
                self.complete_order(oid, packed_by, photo_url, video_url)
                updated.append(oid)
            except Exception:
                errors.append(oid)
        return {"attempted": len(ids), "updated": len(updated), "failed": len(errors), "updated_ids": updated, "failed_ids": errors}

    def complete_order(self, order_id: str, packed_by: str, photo_url: str, video_url: str) -> Dict[str, Any]:
        from datetime import datetime, timezone
        packed_at = datetime.now(timezone.utc).isoformat()
        expr_parts = ["#st = :packed", "packed_by = :pb", "packed_at = :pt", "media_photo_url = :ph", "media_video_url = :vd"]
        names = {"#st": "status"}
        values: Dict[str, Any] = {
            ":packed": {"S": "packed"},
            ":pb": {"S": packed_by},
            ":pt": {"S": packed_at},
            ":ph": {"S": photo_url},
            ":vd": {"S": video_url},
        }
        self.ddb.update_item(
            TableName=self.orders,
            Key={"id": {"S": order_id}},
            UpdateExpression="SET " + ", ".join(expr_parts),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )
        return self.get_order(order_id) or {"id": order_id, "status": "packed", "packed_by": packed_by, "packed_at": packed_at}

    def update_order_items(self, order_id: str, items: List[Dict[str, Any]], summary: Dict[str, Any]) -> Dict[str, Any]:
        # Persist full items array with availability flags and a packing summary
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        self.ddb.update_item(
            TableName=self.orders,
            Key={"id": {"S": order_id}},
            UpdateExpression="SET #it = :it, #ps = :ps, #ua = :ua",
            ExpressionAttributeNames={
                "#it": "items",
                "#ps": "packing_summary",
                "#ua": "updatedAt",
            },
            ExpressionAttributeValues={
                ":it": {"L": [self._marshal_attr(v) for v in items]},
                ":ps": {"M": {k: self._marshal_attr(v) for k, v in summary.items()}},
                ":ua": {"S": now},
            },
        )
        return self.get_order(order_id) or {"id": order_id}

    def _marshal_attr(self, value: Any) -> Dict[str, Any]:
        # Minimal attribute marshaller for common JSON-like types
        if value is None:
            return {"NULL": True}
        if isinstance(value, bool):
            return {"BOOL": value}
        if isinstance(value, (int, float)):
            # store numbers as strings per DynamoDB wire
            return {"N": str(value)}
        if isinstance(value, str):
            return {"S": value}
        if isinstance(value, list):
            return {"L": [self._marshal_attr(v) for v in value]}
        if isinstance(value, dict):
            return {"M": {k: self._marshal_attr(v) for k, v in value.items()}}
        # Fallback to string
        return {"S": str(value)}

    # Profile (Packers)
    def get_packer(self, packer_id: str) -> Optional[Dict[str, Any]]:
        resp = self.ddb.get_item(TableName=self.packers, Key={"packer_id": {"S": packer_id}})
        item = resp.get("Item")
        return self._unmarshal(item) if item else None

    def update_packer(self, packer_id: str, username: Optional[str], email: Optional[str]) -> Dict[str, Any]:
        updates = []
        names: Dict[str, str] = {}
        vals: Dict[str, Any] = {}
        if username:
            updates.append("#un = :un")
            names["#un"] = "username"
            vals[":un"] = {"S": username}
        if email:
            updates.append("#em = :em")
            names["#em"] = "email"
            vals[":em"] = {"S": email}
        expr = "SET " + ", ".join(updates) if updates else "SET dummy = :d"
        if not updates:
            vals[":d"] = {"S": "noop"}
        self.ddb.update_item(
            TableName=self.packers,
            Key={"packer_id": {"S": packer_id}},
            UpdateExpression=expr,
            ExpressionAttributeNames=names if names else None,  # type: ignore[arg-type]
            ExpressionAttributeValues=vals if vals else None,  # type: ignore[arg-type]
        )
        return self.get_packer(packer_id) or {"packer_id": packer_id}

    # Notifications
    def list_notifications(self, user_id: Optional[str], limit: int = 50) -> List[Dict[str, Any]]:
        # If a GSI exists on user_id, use it; else do a scan fallback for demo
        try:
            if user_id:
                resp = self.ddb.query(
                    TableName=self.notifications,
                    IndexName="user_id-index",
                    KeyConditionExpression="#u = :uid",
                    ExpressionAttributeNames={"#u": "user_id"},
                    ExpressionAttributeValues={":uid": {"S": user_id}},
                    Limit=limit,
                    ScanIndexForward=False,
                )
                items = resp.get("Items", [])
            else:
                resp = self.ddb.scan(TableName=self.notifications, Limit=limit)
                items = resp.get("Items", [])
            return [self._unmarshal(i) for i in items]
        except self.ddb.exceptions.ResourceNotFoundException:
            return []


def load_openapi_titles(yaml_text: str) -> Dict[str, Any]:
    spec = yaml.safe_load(yaml_text) or {}
    return {
        "title": (spec.get("info", {}) or {}).get("title", "OpenAPI CLI"),
        "version": (spec.get("info", {}) or {}).get("version", ""),
        "tags": ["System", "Auth", "Orders", "Profile", "Notifications"],
    }


# ------------------------- Menus and Interaction -------------------------

def login_gate(ddb: DDB, meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    title = meta.get("title", "Promodeagro Packer CLI")
    version = meta.get("version", "")
    while True:
        console.print(Panel.fit(f"👋 Welcome to {title} {version}", title="Welcome", style="green"))
        table = Table(title="Start")
        table.add_column("#", justify="right")
        table.add_column("Action")
        table.add_row("1", "Login 🔐")
        table.add_row("2", "Exit 🚪")
        console.print(table)
        ch = IntPrompt.ask("Select", default=2)
        if ch == 2:
            return None
        if ch != 1:
            console.print(Panel.fit("❌ Invalid choice. Please enter 1 or 2.", title="Error", style="red"))
            continue
        # Show available test credentials
        console.print(Panel.fit(
            "Test Credentials:\n"
            "Email: sohailpacker@gmail.com\n"
            "Password: Packer@123\n\n"
            "Note: Set password using:\n"
            "python3 promodeagro_password_tool.py EMAIL PASSWORD",
            title="Login Help", 
            style="cyan"
        ))
        email = Prompt.ask("Email")
        password = Prompt.ask("Password", password=True)
        user = ddb.login_with_password(email, password)
        if not user:
            console.print(Panel.fit("❌ Login failed: invalid email or password", title="Error", style="red"))
            continue
        console.print(Panel.fit("✅ Login successful", title="Success", style="cyan"))
        return user


def app_menu(ddb: DDB, user: Dict[str, Any]) -> None:
    username = user.get("username") or user.get("email") or user.get("id", "")
    console.print(Panel.fit(f"🧑‍💼 Logged in as: {username}", title="Session", style="blue"))
    while True:
        # realtime counts for Orders
        try:
            c_unpacked = ddb.count_orders_by_status("unpacked")
        except Exception:
            c_unpacked = 0
        try:
            c_packed = ddb.count_orders_by_status("packed")
        except Exception:
            c_packed = 0

        table = Table(title="📋 Main Menu")
        table.add_column("#", justify="right")
        table.add_column("Section")
        sections = [f"Orders 📦 (U:{c_unpacked} | P:{c_packed})", "Profile 👤", "Notifications 🔔"]
        for i, s in enumerate(sections, 1):
            table.add_row(str(i), s)
        table.add_row("0", "Logout 🚪")
        console.print(table)
        ch = IntPrompt.ask("Select", default=0)
        if ch == 0:
            console.print("[yellow]👋 Logged out[/yellow]")
            return
        if ch == 1:
            orders_menu(ddb)
        elif ch == 2:
            profile_menu(ddb)
        elif ch == 3:
            notifications_menu(ddb)
        else:
            console.print(Panel.fit("❌ Invalid choice. Enter a number from the menu.", title="Error", style="red"))


def auth_menu(ddb: DDB) -> None:
    while True:
        table = Table(title="Auth")
        table.add_column("#", justify="right")
        table.add_column("Action")
        actions = ["Login (by email)"]
        for i, a in enumerate(actions, 1):
            table.add_row(str(i), a)
        table.add_row("0", "Back")
        console.print(table)
        ch = IntPrompt.ask("Select", default=0)
        if ch == 0:
            return
        if ch == 1:
            email = Prompt.ask("email")
            user = ddb.login_by_email(email)
            console.print(RichJSON.from_data(user) if user else "[yellow]Not found[/yellow]")


def orders_menu(ddb: DDB) -> None:
    while True:
        # Real-time counts
        try:
            unpacked_count = ddb.count_orders_by_status("unpacked")
        except Exception:
            unpacked_count = 0
        try:
            packed_count = ddb.count_orders_by_status("packed")
        except Exception:
            packed_count = 0

        table = Table(title=f"📦 Orders (Unpacked: {unpacked_count} | Packed: {packed_count})")
        table.add_column("#", justify="right")
        table.add_column("Action")
        actions = [
            f"Browse unpacked (paged) 📥 ({unpacked_count})",
            f"Browse packed (paged) 📦✅ ({packed_count})",
            "Show ALL unpacked 📥 (paged)",
            "Show ALL packed 📦✅ (paged)",
            "Get by order_id 🔎",
            f"Start order ✅🖼️🎥 (will update counts)",
            "View completed details 👀",
            "Complete ALL unpacked ✅ (bulk)",
            "Start packing (per item) 🧺",
            "Show packing summary 📊",
        ]
        for i, a in enumerate(actions, 1):
            table.add_row(str(i), a)
        table.add_row("0", "Back ↩️")
        console.print(table)
        ch = IntPrompt.ask("Select", default=0)
        if ch == 0:
            return
        if ch == 1:
            paginate_orders(ddb, status="unpacked")
        elif ch == 2:
            paginate_orders(ddb, status="packed")
        elif ch == 3:
            paginate_orders(ddb, status="unpacked")
        elif ch == 4:
            paginate_orders(ddb, status="packed")
        elif ch == 5:
            oid = Prompt.ask("order_id")
            item = ddb.get_order(oid)
            console.print(print_json(item) if item else "[yellow]⚠️ Not found[/yellow]")
        elif ch == 6:
            oid = Prompt.ask("order_id")
            packed_by = Prompt.ask("packed_by (packer_id)")
            photo = ""
            while not photo.strip():
                photo = Prompt.ask("photo_url (required) 🖼️")
            video = ""
            while not video.strip():
                video = Prompt.ask("video_url (required) 🎥")
            updated = ddb.complete_order(oid, packed_by, photo, video)
            print_json(updated)
        elif ch == 7:
            oid = Prompt.ask("order_id")
            item = ddb.get_order(oid)
            if item and item.get("status") == "packed":
                print_json(item)
            else:
                console.print("[yellow]⚠️ Not packed or not found[/yellow]")
        elif ch == 8:
            packed_by = Prompt.ask("packed_by (packer_id)")
            photo = ""
            while not photo.strip():
                photo = Prompt.ask("photo_url for all (required) 🖼️")
            video = ""
            while not video.strip():
                video = Prompt.ask("video_url for all (required) 🎥")
            summary = ddb.complete_all_unpacked(packed_by, photo, video)
            print_json(summary)
            # show updated realtime counts
            try:
                u = ddb.count_orders_by_status("unpacked")
                p = ddb.count_orders_by_status("packed")
                console.print(Panel.fit(f"Realtime counts → Unpacked: {u} | Packed: {p}", style="cyan"))
            except Exception:
                pass
        elif ch == 9:
            start_packing_per_item(ddb)
        elif ch == 10:
            oid = Prompt.ask("order_id 🔎")
            order = ddb.get_order(oid)
            if not order:
                console.print("[yellow]⚠️ Not found[/yellow]")
            else:
                show_packing_summary(order)


def start_packing_per_item(ddb: DDB) -> None:
    oid = Prompt.ask("order_id to pack (per item) 🔎")
    order = ddb.get_order(oid)
    if not order:
        console.print("[yellow]⚠️ Order not found[/yellow]")
        return
    items = order.get("items") or []
    if not isinstance(items, list) or len(items) == 0:
        console.print("[yellow]⚠️ No items on this order[/yellow]")
        return
    available = 0
    unavailable = 0
    updated_items: List[Dict[str, Any]] = []
    console.print(Panel.fit(f"Packing order {oid} - {len(items)} items", style="cyan"))
    for idx, itm in enumerate(items, start=1):
        # Normalize item dict
        item = dict(itm) if isinstance(itm, dict) else {}
        name = item.get("productName") or item.get("name") or item.get("sku") or f"Item {idx}"
        qty = item.get("quantity") or item.get("quantityUnits") or 1
        console.print(Panel.fit(f"{idx}. {name} (qty: {qty})", style="magenta"))
        table = Table(title="Availability")
        table.add_column("#", justify="right")
        table.add_column("Option")
        table.add_row("1", "Available ✅")
        table.add_row("2", "Unavailable ❌")
        console.print(table)
        choice = IntPrompt.ask("Select", default=1)
        if choice == 1:
            item["availability"] = "available"
            available += 1
        else:
            item["availability"] = "unavailable"
            unavailable += 1
        updated_items.append(item)

    summary = {"available": available, "unavailable": unavailable, "total": len(updated_items)}
    saved = ddb.update_order_items(oid, updated_items, summary)
    console.print(Panel.fit("📝 Item availability saved", style="green"))
    # Show categorized items and summary
    show_packing_summary(saved)
    # Ask to proceed to completion
    if Confirm.ask("Proceed to complete order now? ✅", default=True):
        packed_by = Prompt.ask("packed_by (packer_id)")
        photo = ""
        while not photo.strip():
            photo = Prompt.ask("photo_url (required) 🖼️")
        video = ""
        while not video.strip():
            video = Prompt.ask("video_url (required) 🎥")
        updated = ddb.complete_order(oid, packed_by, photo, video)
        console.print(Panel.fit("🎉 Order completed", style="green"))
        print_json(updated)


def show_packing_summary(order: Dict[str, Any]) -> None:
    oid = order.get("id") or order.get("order_id") or ""
    items = order.get("items") or []
    available_items = []
    unavailable_items = []
    for itm in items:
        item = dict(itm) if isinstance(itm, dict) else {}
        name = item.get("productName") or item.get("name") or item.get("sku") or "(unknown)"
        qty = item.get("quantity") or item.get("quantityUnits") or 1
        status = item.get("availability") or "unknown"
        entry = {"name": name, "qty": qty, "availability": status}
        if status == "available":
            available_items.append(entry)
        elif status == "unavailable":
            unavailable_items.append(entry)
    console.print(Panel.fit(f"📊 Packing summary for {oid}", style="cyan"))
    console.print("[bold]Available items:[/bold]")
    print_json(available_items)
    console.print("[bold]Unavailable items:[/bold]")
    print_json(unavailable_items)
    ps = order.get("packing_summary") or {}
    if ps:
        console.print("[bold]Totals:[/bold]")
        print_json(ps)


def paginate_orders(ddb: DDB, status: str) -> None:
    # Interactive pagination for orders by status
    page_size = 20
    try:
        page_size = int(Prompt.ask("Page size (default 20)", default="20"))
        if page_size <= 0:
            page_size = 20
    except Exception:
        page_size = 20
    history: List[Optional[Dict[str, Any]]] = [None]  # track ExclusiveStartKeys
    idx = 0
    last_key: Optional[Dict[str, Any]] = None
    while True:
        token = history[idx]
        res = ddb.query_orders_page(status=status, limit=page_size, eks=token)
        items = res.get("items", [])
        last_key = res.get("last_key")
        console.print(Panel.fit(f"Status: {status} | Page {idx+1} | Items: {len(items)}", style="cyan"))
        print_json(items)
        # menu
        table = Table(title="Pagination")
        table.add_column("#", justify="right")
        table.add_column("Action")
        table.add_row("1", "Next ▶️")
        table.add_row("2", "Prev ◀️")
        table.add_row("0", "Back ↩️")
        console.print(table)
        choice = IntPrompt.ask("Select", default=0)
        if choice == 0:
            return
        if choice == 1:
            if last_key:
                history.append(last_key)
                idx += 1
            else:
                console.print("[yellow]End of results[/yellow]")
        elif choice == 2:
            if idx > 0:
                idx -= 1
            else:
                console.print("[yellow]Already at first page[/yellow]")


def profile_menu(ddb: DDB) -> None:
    while True:
        table = Table(title="👤 Profile (Packers)")
        table.add_column("#", justify="right")
        table.add_column("Action")
        actions = ["Get packer by packer_id 🔎", "Update packer username/email ✏️"]
        for i, a in enumerate(actions, 1):
            table.add_row(str(i), a)
        table.add_row("0", "Back ↩️")
        console.print(table)
        ch = IntPrompt.ask("Select", default=0)
        if ch == 0:
            return
        if ch == 1:
            pid = Prompt.ask("packer_id")
            item = ddb.get_packer(pid)
            console.print(print_json(item) if item else "[yellow]⚠️ Not found[/yellow]")
        elif ch == 2:
            pid = Prompt.ask("packer_id")
            username = Prompt.ask("username (optional)", default="") or None
            email = Prompt.ask("email (optional)", default="") or None
            updated = ddb.update_packer(pid, username, email)
            print_json(updated)


def notifications_menu(ddb: DDB) -> None:
    while True:
        table = Table(title="🔔 Notifications")
        table.add_column("#", justify="right")
        table.add_column("Action")
        actions = ["List all (scan) 📜", "List by user_id (GSI if present) 👤"]
        for i, a in enumerate(actions, 1):
            table.add_row(str(i), a)
        table.add_row("0", "Back ↩️")
        console.print(table)
        ch = IntPrompt.ask("Select", default=0)
        if ch == 0:
            return
        if ch == 1:
            items = ddb.list_notifications(user_id=None)
            print_json(items)
        elif ch == 2:
            uid = Prompt.ask("user_id")
            items = ddb.list_notifications(user_id=uid)
            print_json(items)


def main() -> None:
    meta = load_openapi_titles(OPENAPI_YAML)
    ddb = DDB()
    user = login_gate(ddb, meta)
    if not user:
        return
    app_menu(ddb, user)


if __name__ == "__main__":
    main()


