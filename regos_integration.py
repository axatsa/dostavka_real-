import logging
import requests
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class REGOSIntegration:
    def __init__(self, api_key: str, base_url: str = "https://regos.uz/api/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def create_order(self, order_data: Dict) -> Optional[Dict]:
        """
        Create a new order in REGOS system
        
        Args:
            order_data: Dictionary containing order details
                {
                    'user': {
                        'name': str,
                        'phone': str
                    },
                    'delivery_address': str,
                    'delivery_date': str (YYYY-MM-DD),
                    'delivery_time': str (HH:MM),
                    'items': List[Dict],
                    'total_amount': float,
                    'external_id': str
                }
                
        Returns:
            Dict containing REGOS order data or None if failed
        """
        url = f"{self.base_url}/orders"
        
        try:
            # Format items for REGOS
            items = []
            for item in order_data['items']:
                items.append({
                    'name': item['name'],
                    'quantity': item['quantity'],
                    'price': item['price'],
                    'total': item['quantity'] * item['price']
                })
            
            payload = {
                'customer': {
                    'name': order_data['user']['name'],
                    'phone': order_data['user']['phone']
                },
                'delivery': {
                    'address': order_data['delivery_address'],
                    'date': order_data['delivery_date'],
                    'time': order_data['delivery_time']
                },
                'items': items,
                'total_amount': order_data['total_amount'],
                'external_id': str(order_data['external_id']),
                'created_at': datetime.now().isoformat()
            }
            
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating REGOS order: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None
    
    def get_order_status(self, regos_order_id: str) -> Optional[Dict]:
        """
        Get order status from REGOS
        
        Args:
            regos_order_id: The REGOS order ID
            
        Returns:
            Dict containing order status or None if failed
        """
        url = f"{self.base_url}/orders/{regos_order_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting REGOS order status: {e}")
            return None
    
    def update_order_status(self, regos_order_id: str, status: str, 
                          comment: str = "") -> bool:
        """
        Update order status in REGOS
        
        Args:
            regos_order_id: The REGOS order ID
            status: New status
            comment: Optional comment
            
        Returns:
            bool: True if successful, False otherwise
        """
        url = f"{self.base_url}/orders/{regos_order_id}/status"
        
        try:
            payload = {
                'status': status,
                'comment': comment,
                'updated_at': datetime.now().isoformat()
            }
            
            response = requests.put(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error updating REGOS order status: {e}")
            return False
    
    def sync_orders(self, db):
        """
        Sync local orders with REGOS system
        
        Args:
            db: Database instance
            
        Returns:
            List of sync results
        """
        results = []
        orders_to_sync = db.get_orders_for_regos_sync()
        
        for order in orders_to_sync:
            # Get user info
            user = db.get_user(order['user_id'])
            if not user:
                logger.error(f"User not found for order {order['id']}")
                continue
                
            order_data = {
                'user': {
                    'name': user['name'],
                    'phone': user['phone']
                },
                'delivery_address': order['delivery_address'],
                'delivery_date': order['delivery_date'],
                'delivery_time': order['delivery_time'],
                'items': order['items'],
                'total_amount': order['total_amount'],
                'external_id': order['id']
            }
            
            # Create order in REGOS
            result = self.create_order(order_data)
            
            if result and 'id' in result:
                db.set_regos_order_id(order['id'], result['id'])
                results.append({
                    'order_id': order['id'],
                    'regos_order_id': result['id'],
                    'status': 'success',
                    'message': 'Order synced successfully'
                })
            else:
                results.append({
                    'order_id': order['id'],
                    'status': 'error',
                    'message': 'Failed to sync order with REGOS'
                })
        
        return results
