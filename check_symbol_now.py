#!/usr/bin/env python3

import os
import requests
from datetime import datetime

api_key = os.getenv('TIINGO_API_KEY', 'fd22b372d0196fa709b41e370617c5f918bd3c36')

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Token {api_key}'
}

print(f'GEG Real-time IEX Data - {datetime.now().strftime("%Y-%m-%d %H:%M:%S EST")}')
print('=' * 50)

response = requests.get('https://api.tiingo.com/iex/GEG', headers=headers, timeout=10)

if response.status_code == 200:
    data = response.json()
    if isinstance(data, list) and data:
        quote = data[0]
        
        print(f'ALL AVAILABLE FIELDS:')
        for key, value in quote.items():
            print(f'  {key}: {value}')
        
        print(f'\nLOOKING FOR EXTENDED HOURS SPECIFIC FIELDS:')
        extended_fields = ['extendedPrice', 'extendedChange', 'extendedChangePercent', 
                          'extendedMarket', 'extendedSession', 'afterHours', 'preMarket']
        for field in extended_fields:
            if field in quote:
                print(f'  {field}: {quote[field]}')
        
        current_price = quote.get('tngoLast') or quote.get('mid') or quote.get('bidPrice')
        print(f'\nCURRENT GEG PRICE: ${current_price}')
        
else:
    print(f'Error: {response.status_code} - {response.text}')