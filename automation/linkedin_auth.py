"""
automation/linkedin_auth.py — LinkedIn 1-Click Interactive Session Authenticator
Provides standalone CLI for securely logging into LinkedIn via Playwright,
solving CAPTCHA / 2FA naturally, and persisting cookies for automated runs.
"""

import sys
import asyncio
import argparse
from rich.console import Console
from rich.panel import Panel
from automation.browser_manager import (
    DEFAULT_LINKEDIN_SESSION_PATH,
    BrowserManager,
    interactive_linkedin_login
)

console = Console()


async def main_async():
    parser = argparse.ArgumentParser(description="LinkedIn Persistent Session Authenticator")
    parser.add_argument("--session-path", default=DEFAULT_LINKEDIN_SESSION_PATH, help="Path to save session JSON")
    parser.add_argument("--timeout", type=int, default=180, help="Max seconds to wait for login (default: 180)")
    parser.add_argument("--check", action="store_true", help="Check if current session is valid")
    parser.add_argument("--clear", action="store_true", help="Clear saved session file")

    args = parser.parse_args()

    if args.check:
        is_auth = BrowserManager.is_linkedin_authenticated(args.session_path)
        if is_auth:
            console.print(Panel(f"[bold green]✓ LinkedIn is CONNECTED & AUTHENTICATED[/bold green]\nSession file: [cyan]{args.session_path}[/cyan]", title="LinkedIn Session Status"))
            sys.exit(0)
        else:
            console.print(Panel(f"[bold yellow]✗ LinkedIn is NOT authenticated or session expired[/bold yellow]\nSession file: [cyan]{args.session_path}[/cyan]", title="LinkedIn Session Status"))
            sys.exit(1)

    if args.clear:
        cleared = BrowserManager.clear_linkedin_session(args.session_path)
        if cleared:
            console.print(f"[bold green]✓ Cleared session file: {args.session_path}[/bold green]")
        else:
            console.print(f"[dim]No active session file found at: {args.session_path}[/dim]")
        sys.exit(0)

    console.print(Panel.fit(
        "[bold cyan]AutoJobPilot — LinkedIn 1-Click Session Authenticator[/bold cyan]\n"
        "• A visible browser window will open to [link=https://www.linkedin.com/login]linkedin.com/login[/link].\n"
        "• Enter your email, password, and any 2FA / CAPTCHA challenge in the browser.\n"
        "• Once authenticated, your session cookies ([bold]li_at[/bold]) will be securely saved locally.",
        title="🔐 LinkedIn Authentication"
    ))

    def on_progress(msg: str):
        console.print(f"[cyan]→[/cyan] {msg}")

    result = await interactive_linkedin_login(
        session_path=args.session_path,
        timeout_seconds=args.timeout,
        on_progress=on_progress
    )

    if result["success"]:
        console.print(Panel(
            f"[bold green]🎉 SUCCESS: LinkedIn Session Authenticated![/bold green]\n\n"
            f"Saved to: [bold cyan]{result['session_path']}[/bold cyan]\n"
            "Subsequent automated runs (Spark Agent & Streamlit) will now execute with your active profile.",
            title="Authentication Complete"
        ))
    else:
        console.print(Panel(
            f"[bold red]❌ Failed to authenticate LinkedIn:[/bold red] {result.get('message')}\n"
            "Please run the command again and complete the login within the timeout period.",
            title="Authentication Failed"
        ))
        sys.exit(1)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
