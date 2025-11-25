#!/usr/bin/env python3
"""
WebSocket Test Script for CRM Notifications

This script tests the WebSocket connection for receiving real-time notifications.
It logs in via REST API, connects to the WebSocket, and listens for notifications.

Prerequisites:
    pip install websockets requests

Usage:
    python test_websocket.py --username <username> --password <password> --url <base_url>
    
Example:
    python test_websocket.py --username admin --password admin123 --url http://localhost:8000
"""

import asyncio
import json
import argparse
import sys

try:
    import requests
except ImportError:
    print("❌ Error: 'requests' library not found. Install it with: pip install requests")
    sys.exit(1)

try:
    from websockets.client import connect
    from websockets.exceptions import ConnectionClosed, InvalidURI
except ImportError:
    print("❌ Error: 'websockets' library not found. Install it with: pip install websockets")
    sys.exit(1)


class WebSocketTester:
    def __init__(self, base_url, username, password):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.ws_url = None
        self.session_id = None
        
    def login(self):
        """Login via REST API and get session cookie"""
        print(f"🔐 Logging in as {self.username}...")
        
        login_url = f"{self.base_url}/api/accounts/auth/login/"
        
        try:
            response = self.session.post(
                login_url,
                json={
                    'username': self.username,
                    'password': self.password
                },
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Login successful!")
                print(f"   User ID: {data.get('user', {}).get('id', 'N/A')}")
                print(f"   Email: {data.get('user', {}).get('email', 'N/A')}")
                
                # Get session ID from cookies
                self.session_id = self.session.cookies.get('sessionid')
                if self.session_id:
                    print(f"   Session ID: {self.session_id[:20]}...")
                else:
                    print("   ⚠️  Warning: No session cookie found. Using JWT authentication.")
                
                return True
            else:
                print(f"❌ Login failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def get_ws_url(self):
        """Construct WebSocket URL"""
        # Convert http/https to ws/wss
        if self.base_url.startswith('https://'):
            ws_base = self.base_url.replace('https://', 'wss://')
        else:
            ws_base = self.base_url.replace('http://', 'ws://')
        
        self.ws_url = f"{ws_base}/ws/crm/notifications/"
        return self.ws_url
    
    async def test_websocket(self):
        """Connect to WebSocket and listen for notifications"""
        ws_url = self.get_ws_url()
        print(f"\n🔌 Connecting to WebSocket: {ws_url}")
        
        # Prepare headers with session cookie and origin
        headers = {}
        if self.session_id:
            headers['Cookie'] = f'sessionid={self.session_id}'
        
        # Add Origin header to match the base URL (helps with origin validation)
        if self.base_url.startswith('https://'):
            origin = self.base_url
        else:
            origin = self.base_url
        headers['Origin'] = origin
        
        try:
            async with connect(ws_url, extra_headers=headers) as websocket:
                print("✅ WebSocket connected!")
                print("\n📡 Listening for notifications...")
                print("   (Press Ctrl+C to stop)\n")
                
                # Send initial ping
                await websocket.send(json.dumps({'command': 'ping'}))
                
                # Request unread count
                await websocket.send(json.dumps({'command': 'get_unread_count'}))
                
                try:
                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            await self.handle_message(data)
                        except json.JSONDecodeError:
                            print(f"⚠️  Received non-JSON message: {message}")
                        except Exception as e:
                            print(f"❌ Error processing message: {e}")
                            
                except KeyboardInterrupt:
                    print("\n\n👋 Disconnecting...")
                    await websocket.close()
                    
        except ConnectionClosed:
            print("❌ WebSocket connection closed")
        except InvalidURI:
            print(f"❌ Invalid WebSocket URL: {ws_url}")
        except Exception as e:
            print(f"❌ WebSocket error: {e}")
            import traceback
            traceback.print_exc()
    
    async def handle_message(self, data):
        """Handle incoming WebSocket messages"""
        msg_type = data.get('type')
        
        if msg_type == 'connection_established':
            print(f"✅ {data.get('message', 'Connected')}")
            print(f"   User ID: {data.get('user_id', 'N/A')}\n")
            
        elif msg_type == 'notification':
            notification = data.get('notification', {})
            print("🔔 NEW NOTIFICATION RECEIVED!")
            print(f"   Title: {notification.get('title', 'N/A')}")
            print(f"   Message: {notification.get('message', 'N/A')}")
            print(f"   Type: {notification.get('notification_type', 'N/A')}")
            print(f"   ID: {notification.get('id', 'N/A')}")
            print(f"   Read: {notification.get('is_read', False)}")
            print()
            
        elif msg_type == 'unread_count':
            count = data.get('count', 0)
            print(f"📊 Unread notifications: {count}\n")
            
        elif msg_type == 'pong':
            print("💓 Pong received (connection alive)\n")
            
        elif msg_type == 'mark_as_read_response':
            success = data.get('success', False)
            notif_id = data.get('notification_id', 'N/A')
            status = "✅" if success else "❌"
            print(f"{status} Mark as read response for notification {notif_id}\n")
            
        elif msg_type == 'error':
            print(f"❌ Error: {data.get('message', 'Unknown error')}\n")
            
        else:
            print(f"📨 Received message type: {msg_type}")
            print(f"   Data: {json.dumps(data, indent=2)}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Test WebSocket connection for CRM notifications'
    )
    parser.add_argument(
        '--username',
        required=True,
        help='Username for login'
    )
    parser.add_argument(
        '--password',
        required=True,
        help='Password for login'
    )
    parser.add_argument(
        '--url',
        default='http://localhost:8000',
        help='Base URL of the CRM server (default: http://localhost:8000)'
    )
    
    args = parser.parse_args()
    
    tester = WebSocketTester(args.url, args.username, args.password)
    
    # Login first
    if not tester.login():
        sys.exit(1)
    
    # Test WebSocket connection
    try:
        asyncio.run(tester.test_websocket())
    except KeyboardInterrupt:
        print("\n\n👋 Test interrupted by user")
        sys.exit(0)


if __name__ == '__main__':
    main()

