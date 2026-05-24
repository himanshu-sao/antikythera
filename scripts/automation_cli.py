import argparse
import sys
import os

# Add project root to sys.path so we can import agents
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.automation_manager import AutomationManager
import json

def main():
    parser = argparse.ArgumentParser(description="Automation Registry CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Add command
    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("--id", required=True)
    add_parser.add_argument("--name", required=True)
    add_parser.add_argument("--description", required=True)
    add_parser.add_argument("--intent_type", choices=["PROMPT", "SCRIPT"], required=True)
    add_parser.add_argument("--intent_content", required=True)
    add_parser.add_argument("--mode", choices=["ONCE", "RECURRING"], required=True)
    add_parser.add_argument("--trigger_type", choices=["TIMER", "EVENT", "MANUAL"], required=True)
    add_parser.add_argument("--schedule", help="Cron schedule for TIMER")
    add_parser.add_argument("--source", help="Source for EVENT (file, webhook)")
    add_parser.add_argument("--pattern", help="Glob pattern for EVENT")
    add_parser.add_argument("--path", help="Path for EVENT")

    # List command
    subparsers.add_parser("list")

    # Get command
    get_parser = subparsers.add_parser("get")
    get_parser.add_argument("--id", required=True)

    # Update command
    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("--id", required=True)
    update_parser.add_argument("--status", required=True)
    update_parser.add_argument("--outcome", help="SUCCESS/FAILURE/N/A")
    update_parser.add_argument("--log", help="Path to log")

    # Remove command
    remove_parser = subparsers.add_parser("remove")
    remove_parser.add_argument("--id", required=True)

    args = parser.parse_args()
    manager = AutomationManager()

    if args.command == "add":
        metadata = {"name": args.name, "description": args.description}
        intent = {"type": args.intent_type, "content": args.intent_content}
        trigger_config = {}
        if args.trigger_type == "TIMER":
            trigger_config["schedule"] = args.schedule
        elif args.trigger_type == "EVENT":
            trigger_config["source"] = args.source
            trigger_config["pattern"] = args.pattern
            trigger_config["path"] = args.path
        
        execution_policy = {
            "mode": args.mode,
            "trigger": {
                "type": args.trigger_type,
                "config": trigger_config
            }
        }
        success = manager.add_task(args.id, metadata, intent, execution_policy)
        print("SUCCESS" if success else "FAILED")

    elif args.command == "list":
        tasks = manager.list_tasks()
        print(json.dumps(tasks, indent=2))

    elif args.command == "get":
        task = manager.get_task(args.id)
        if task:
            print(json.dumps(task, indent=2))
        else:
            print("NOT_FOUND")

    elif args.command == "update":
        success = manager.update_task_status(args.id, args.status, args.outcome, args.log)
        print("SUCCESS" if success else "FAILED")

    elif args.command == "remove":
        success = manager.remove_task(args.id)
        print("SUCCESS" if success else "FAILED")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
