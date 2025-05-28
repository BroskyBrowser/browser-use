#!/usr/bin/env python3
"""
Test script for Turnstile interaction using DOMService.
This test navigates to the Turnstile page, builds a DOM tree, finds the checkbox and clicks it using CDP.
"""

import asyncio
import json
import logging
import os
import sys
import time

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from playwright.async_api import Browser, BrowserContext, CDPSession, Page, async_playwright

from browser_use.dom.dom_optimized.service import DOMService
from browser_use.dom.dom_optimized.views import DOMElementNode, DOMTextNode, DOMTree

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TurnstileInteractionTest:
	"""Test class for Turnstile checkbox interaction"""

	def __init__(self, use_remote_browser: bool = False):
		self.page: Page | None = None
		self.playwright: async_playwright | None = None
		self.browser: Browser | None = None
		self.context: BrowserContext | None = None
		self.cdp_session: CDPSession | None = None
		self.dom_service: DOMService | None = None
		self.dom_tree: DOMTree | None = None
		self.sessions: dict[str, CDPSession] = {}
		self.use_remote_browser = use_remote_browser
		# self.remote_ws_endpoint = 'wss://connect.anchorbrowser.io?apiKey=sk-7e4807a5d6c99bbadbdb94a3cf85a3e2&sessionId=465b7613-0f4c-42c3-b93f-22c097a7125a'
		# self.remote_ws_endpoint = 'wss://brd-customer-hl_eb15d933-zone-scraping_browser1:ueb57qu3r57j@brd.superproxy.io:9222'
		self.remote_ws_endpoint = 'wss://connect.usw2.browserbase.com?signingKey=eyJhbGciOiJBMjU2S1ciLCJlbmMiOiJBMjU2R0NNIn0.1W4xQ_BSR8xZxo9sZNJIxfrQkCxzY-JR5zJ1PqkudXLPDXpuia6ngA.3f2PYGmBOm_g3-6V.wAPZz1fpDZ3ZhGjb1FCj0pvIc5489-3XHXNUjaQypQ8SkORybuqwHYtLJ0NGx6OYSPpZXvNG9VALciduYWprB4UIYDXxbFMzp17F89iI5Ylk_OqruFQ_z9ySgknTV9cuOmCgBgpdr02s6h2geOIzUgoSUmRaETWbhjmyWcD9P-NX6D-MfdTKK7F-9URrEi_AyJbL3JUXLOS6PxqvWxT6r_FVjcdR8gfBq4ii-pDS7tiRTzCd_8QEJxS15PoQ-W7s6DvPbRW47DnemdJh0t3KwYA9G5nC1KxqVpICsYhQj53eWXZuqCqTrIMMF2LK2qV311Fj0aE7IwrfOMsnSnj5qRc.z5dSLV6X1PKXFGfrGTNvQA'

	async def setup(self):
		"""Setup browser and navigate to Turnstile page"""
		print('🚀 Setting up browser and navigating to Turnstile...')

		self.playwright = await async_playwright().start()

		if self.use_remote_browser:
			print(f'🌐 Connecting to remote browser at: {self.remote_ws_endpoint}')
			self.browser = await self.playwright.chromium.connect_over_cdp(self.remote_ws_endpoint)
			# Get existing context or create new one
			contexts = self.browser.contexts
			if contexts:
				self.context = contexts[0]
			else:
				self.context = await self.browser.new_context()
			# Get existing page or create new one
			pages = self.context.pages
			if pages:
				self.page = pages[0]
			else:
				self.page = await self.context.new_page()
		else:
			print('💻 Using local Chrome browser')
			self.browser = await self.playwright.chromium.launch(
				headless=False,  # Show browser for debugging
				args=[
					'--remote-debugging-port=9222',
					'--disable-blink-features=AutomationControlled',
				],
				channel='chrome',  # Use Google Chrome instead of Chromium
			)
			self.context = await self.browser.new_context(
				viewport={'width': 1920, 'height': 1080},
				user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
			)
			self.page = await self.context.new_page()

		self.cdp_session = await self.context.new_cdp_session(self.page)

		# Navigate to Turnstile page
		# url = 'https://seleniumbase.io/apps/turnstile'
		# url = 'https://ahrefs.com/backlink-checker/?input=www.he-tk.de&amp;mode=subdomains'
		# url = 'https://www.hapag-lloyd.com/en/online-business/track/track-by-booking-solution.html?blno=HLCUSGN2406BVAA4'
		url = 'https://www.gamelife.it/ccpk0126-carte-pokemon-paradise-dragona-busta-jp.html'
		print(f'🌐 Navigating to: {url}')
		await self.page.goto(url)

		# Wait for page load with longer timeout
		try:
			await self.page.wait_for_load_state('load', timeout=60000)
			print('📄 DOM content loaded')
		except:
			print('⚠️  DOM content load timeout, continuing anyway...')

		print('⏳ Waiting 6 seconds for Turnstile to fully load...')
		await asyncio.sleep(5)

	async def build_dom_tree(self):
		"""Build DOM tree using DOMService"""
		print('🌳 Building DOM tree...')

		self.dom_service = DOMService(self.page, self.context, self.cdp_session)
		self.dom_tree = await self.dom_service.build_dom_tree()

		# Get statistics
		all_elements = self.dom_tree.get_all_elements()
		iframe_elements = [e for e in all_elements if e.tag == 'iframe']
		checkbox_elements = [e for e in all_elements if e.tag == 'input' and e.attributes.get('type') == 'checkbox']

		print('📊 DOM Statistics:')
		print(f'   Total elements: {len(all_elements)}')
		print(f'   Iframe elements: {len(iframe_elements)}')
		print(f'   Checkbox elements: {len(checkbox_elements)}')

		# Debug: print all input elements found
		input_elements = [e for e in all_elements if e.tag == 'input']
		print(f'   Input elements: {len(input_elements)}')
		for i, inp in enumerate(input_elements):
			print(f'     Input {i + 1}: type={inp.attributes.get("type", "unknown")}, attrs={inp.attributes}')

		return self.dom_tree

	async def click_checkbox_with_cdp(self, checkbox_element: DOMElementNode):
		"""Click checkbox using CDP commands"""

		try:
			session = await checkbox_element.get_session(self.page)

			await session.send('DOM.getDocument', {'depth': -1, 'pierce': True})

			# Get box model for the checkbox
			print(f'📐 Getting box model for node {checkbox_element.node_id}...')
			box_model_result = await session.send('DOM.getBoxModel', {'nodeId': checkbox_element.node_id})

			model = box_model_result.get('model')
			if not model or not model.get('content'):
				print('❌ Could not get box model for checkbox')
				return False

			# Calculate center coordinates
			content = model['content']
			if len(content) < 8:
				print('❌ Invalid box model content')
				return False

			x = (content[0] + content[2]) / 2
			y = (content[1] + content[5]) / 2

			print(f'🎯 Clicking at coordinates ({x:.1f}, {y:.1f})')

			# Perform mouse click: mousePressed + mouseReleased
			mouse_params = {'type': 'mousePressed', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1}

			await session.send('Input.dispatchMouseEvent', mouse_params)

			mouse_params['type'] = 'mouseReleased'
			await session.send('Input.dispatchMouseEvent', mouse_params)

			print('✅ Checkbox clicked successfully!')

			# Wait a moment to see the result
			await asyncio.sleep(2)

			await session.detach()

			return True

		except Exception as e:
			print(f'❌ Error clicking checkbox: {e}')
			return False

	async def save_results(self):
		"""Save DOM tree results to file"""
		if not self.dom_tree:
			return

		# Convert DOM tree to serializable format
		def element_to_dict(element):
			if isinstance(element, DOMTextNode):
				return {'type': 'text', 'content': element.text}
			elif isinstance(element, DOMElementNode):
				return {
					'type': 'element',
					'tag': element.tag,
					'attributes': element.attributes,
					'text_content': element.text_content,
					'node_id': getattr(element, 'node_id', None),
					'children': [element_to_dict(child) for child in element.children],
				}
			return None

		results = {
			'url': 'https://ahrefs.com/backlink-checker/?input=www.he-tk.de&amp;mode=subdomains',
			'timestamp': asyncio.get_event_loop().time(),
			'dom_tree': element_to_dict(self.dom_tree.root) if self.dom_tree.root else None,
		}

		filename = 'turnstile_interaction_results.json'
		with open(filename, 'w') as f:
			json.dump(results, f, indent=2)

		print(f'💾 Results saved to {filename}')

	async def cleanup(self):
		"""Cleanup resources"""
		print('🧹 Cleaning up...')

		# Close all iframe sessions
		for session in self.sessions.values():
			try:
				await session.detach()
			except:
				pass

		if self.cdp_session:
			try:
				await self.cdp_session.detach()
			except:
				pass

		if self.browser:
			await self.browser.close()

		if self.playwright:
			await self.playwright.stop()

	async def run_test(self):
		"""Run the complete test"""
		try:
			print('🔬 Starting Turnstile Interaction Test')
			print('=' * 60)

			# Setup
			await self.setup()

			# Build DOM tree
			start_time = time.time()
			await self.build_dom_tree()
			end_time = time.time()
			print(f'🌳 DOM tree built in {end_time - start_time:.2f} seconds')

			# Find checkbox
			checkbox_elements = self.dom_tree.get_element_by_condition(
				lambda e: e.tag == 'input' and e.attributes.get('type') == 'checkbox' and 'cloudflare.com' in e.frame_url
			)
			checkbox_element = checkbox_elements[0] if checkbox_elements else None

			if checkbox_element:
				print(f'🖱️  Attempting to click checkbox in {checkbox_element.frame_url}...')
				# Click checkbox
				success = await self.click_checkbox_with_cdp(checkbox_element)

				if success:
					print('🎉 Test PASSED! Checkbox was found and clicked successfully.')
				else:
					print('❌ Test FAILED! Could not click checkbox.')
			else:
				print('❌ Test FAILED! No checkbox found in DOM tree.')

			# Save results
			await asyncio.sleep(10)
			# print(self.dom_tree.translate_all_to_llm(format='csv'))
			print('DOM Tree nodes: ', len(self.dom_tree.get_all_elements()))
			await self.save_results()

		except Exception as e:
			print(f'💥 Test failed with exception: {e}')
			logger.exception('Test exception details:')

		finally:
			await self.cleanup()


async def main():
	"""Main test function"""
	# Change this to True to use remote browser, False for local
	USE_REMOTE_BROWSER = False

	test = TurnstileInteractionTest(use_remote_browser=USE_REMOTE_BROWSER)
	await test.run_test()


if __name__ == '__main__':
	asyncio.run(main())
