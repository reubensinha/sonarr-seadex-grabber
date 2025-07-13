"""Webhook server to receive Sonarr events."""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from utils import log


class SonarrWebhookHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Sonarr webhooks."""

    # Callback function to be set by the main application
    event_callback = None

    def do_POST(self):
        """Handle POST requests from Sonarr webhooks."""
        try:
            # Get the content length
            content_length = int(self.headers.get("Content-Length", 0))

            # Read the POST data
            post_data = self.rfile.read(content_length)

            # Parse JSON payload
            try:
                webhook_data = json.loads(post_data.decode("utf-8"))
            except json.JSONDecodeError as e:
                log(f"Failed to parse webhook JSON: {e}")
                self.send_response(400)
                self.end_headers()
                return

            # Log the webhook event
            event_type = webhook_data.get("eventType", "Unknown")
            log(f"Received Sonarr webhook: {event_type}")

            # Process the webhook event
            self.process_webhook(webhook_data)

            # Send success response
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "success"}')

        except Exception as e:
            log(f"Error processing webhook: {e}")
            self.send_response(500)
            self.end_headers()

    def do_GET(self):
        """Handle GET requests (health check)."""
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Sonarr Webhook Server is running")

    def process_webhook(self, webhook_data):
        """Process the webhook data and trigger appropriate actions."""
        event_type = webhook_data.get("eventType")

        # Events that should trigger a series update
        trigger_events = [
            "SeriesAdd",  # Series added
            "SeriesDelete",  # Series deleted
            "SeriesEdit",  # Series edited (monitoring status might change)
            "Health",  # Health check (could indicate monitoring changes)
            "Test",  # Test webhook
        ]

        if event_type in trigger_events:
            log(f"Webhook event '{event_type}' triggers series update")

            # Call the callback function if set
            if self.event_callback:
                try:
                    # Run callback in a separate thread to avoid blocking the webhook response
                    callback_thread = threading.Thread(
                        target=self.event_callback,
                        args=(event_type, webhook_data),
                        daemon=True,
                    )
                    callback_thread.start()
                except Exception as e:
                    log(f"Error calling webhook callback: {e}")
            else:
                log("No webhook callback function set")
        else:
            log(f"Webhook event '{event_type}' ignored (no action needed)")

    def log_message(self, format, *args):
        """Override to use our logging system instead of printing to stderr."""
        log(f"Webhook server: {format % args}")


class WebhookServer:
    """Webhook server manager."""

    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.server = None
        self.server_thread = None

    def set_event_callback(self, callback_func):
        """Set the callback function to be called when relevant events are received."""
        SonarrWebhookHandler.event_callback = callback_func

    def start(self):
        """Start the webhook server."""
        try:
            self.server = HTTPServer((self.host, self.port), SonarrWebhookHandler)
            log(f"Starting webhook server on {self.host}:{self.port}")

            # Start server in a separate thread
            self.server_thread = threading.Thread(
                target=self.server.serve_forever, daemon=True
            )
            self.server_thread.start()

            log("Webhook server started successfully")
            log(f"Configure Sonarr webhook URL: http://{self.host}:{self.port}/webhook")

        except Exception as e:
            log(f"Failed to start webhook server: {e}")
            raise

    def stop(self):
        """Stop the webhook server."""
        if self.server:
            log("Stopping webhook server...")
            self.server.shutdown()
            self.server.server_close()

            if self.server_thread:
                self.server_thread.join(timeout=5)

            log("Webhook server stopped")

    def is_running(self):
        """Check if the webhook server is running."""
        return (
            self.server is not None
            and self.server_thread is not None
            and self.server_thread.is_alive()
        )
