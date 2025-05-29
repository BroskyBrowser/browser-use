#!/usr/bin/env python3
"""
Test script for PerimeterX interaction using DOMService.
This test navigates to the Sam's Club login page, builds a DOM tree, finds the "Press & Hold" button and right-clicks it using CDP.
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


class PerimeterXInteractionTest:
	"""Test class for PerimeterX captcha interaction"""

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
		self.remote_ws_endpoint = 'wss://connect.usw2.browserbase.com?signingKey=eyJhbGciOiJBMjU2S1ciLCJlbmMiOiJBMjU2R0NNIn0.1W4xQ_BSR8xZxo9sZNJIxfrQkCxzY-JR5zJ1PqkudXLPDXpuia6ngA.3f2PYGmBOm_g3-6V.wAPZz1fpDZ3ZhGjb1FCj0pvIc5489-3XHXNUjaQypQ8SkORybuqwHYtLJ0NGx6OYSPpZXvNG9VALciduYWprB4UIYDXxbFMzp17F89iI5Ylk_OqruFQ_z9ySgknTV9cuOmCgBgpdr02s6h2geOIzUgoSUmRaETWbhjmyWcD9P-NX6D-MfdTKK7F-9URrEi_AyJbL3JUXLOS6PxqvWxT6r_FVjcdR8gfBq4ii-pDS7tiRTzCd_8QEJxS15PoQ-W7s6DvPbRW47DnemdJh0t3KwYA9G5nC1KxqVpICsYhQj53eWXZuqCqTrIMMF2LK2qV311Fj0aE7IwrfOMsnSnj5qRc.z5dSLV6X1PKXFGfrGTNvQA'

	async def setup(self):
		"""Setup browser and navigate to Sam's Club login page"""
		print("🚀 Setting up browser and navigating to Sam's Club...")

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
					'--incognito',  # Launch in incognito mode
				],
				channel='chrome',  # Use Google Chrome instead of Chromium
			)
			self.context = await self.browser.new_context(
				viewport={'width': 1920, 'height': 1080},
				user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
			)
			self.page = await self.context.new_page()

		self.cdp_session = await self.context.new_cdp_session(self.page)

		# Navigate to Sam's Club login page
		url = 'https://www.samsclub.com/login'
		print(f'🌐 Navigating to: {url}')
		await self.page.goto(url)

		# Wait for page load with longer timeout
		try:
			await self.page.wait_for_load_state('load', timeout=60000)
			print('📄 DOM content loaded')
		except:
			print('⚠️  DOM content load timeout, continuing anyway...')

		print('⏳ Waiting 5 seconds for PerimeterX popup to appear...')
		await asyncio.sleep(5)

	async def build_dom_tree(self):
		"""Build DOM tree using DOMService"""
		print('🌳 Building DOM tree...')

		self.dom_service = DOMService(self.page, self.context, self.cdp_session)
		self.dom_tree = await self.dom_service.build_dom_tree()

		# Get statistics
		all_elements = self.dom_tree.get_all_elements()
		iframe_elements = [e for e in all_elements if e.tag == 'iframe']
		p_elements = [e for e in all_elements if e.tag == 'p']

		print('📊 DOM Statistics:')
		print(f'   Total elements: {len(all_elements)}')
		print(f'   Iframe elements: {len(iframe_elements)}')
		print(f'   P elements: {len(p_elements)}')

		# Debug: print iframe information
		print('   Iframe details:')
		for i, iframe in enumerate(iframe_elements):
			style = iframe.attributes.get('style', '')
			computed_styles = getattr(iframe, 'computed_styles', {})
			computed_display = computed_styles.get('display', 'unknown')
			print(f'     Iframe {i + 1}: node_id={iframe.node_id}, computed_display={computed_display}, style="{style[:50]}..."')

		# Debug: print all p elements found
		print('   P elements content:')
		for i, p in enumerate(p_elements):
			text = p.text_content or ''
			print(f'     P {i + 1}: text="{text}" node_id={p.node_id}, frame_url={p.frame_url}')

		return self.dom_tree

	async def click_element_with_cdp(self, press_hold_element: DOMElementNode):
		"""Click the Press & Hold button using CDP commands"""

		try:
			session = await press_hold_element.get_session(self.page)

			await session.send('DOM.getDocument', {'depth': -1, 'pierce': True})

			# Get box model for the element
			print(f'📐 Getting box model for node {press_hold_element.node_id}...')
			box_model_result = await session.send('DOM.getBoxModel', {'nodeId': press_hold_element.node_id})

			model = box_model_result.get('model')
			if not model or not model.get('content'):
				print('❌ Could not get box model for element')
				return False

			# Calculate center coordinates
			content = model['content']
			if len(content) < 8:
				print('❌ Invalid box model content')
				return False

			x = (content[0] + content[2]) / 2
			y = (content[1] + content[5]) / 2

			print(f'🎯 Right-clicking at coordinates ({x:.1f}, {y:.1f})')

			# Perform left-click: mousePressed + mouseReleased with left button
			mouse_params = {'type': 'mousePressed', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1}

			await session.send('Input.dispatchMouseEvent', mouse_params)

			# Hold for a moment to simulate "Press & Hold"
			await asyncio.sleep(7)

			mouse_params['type'] = 'mouseReleased'
			await session.send('Input.dispatchMouseEvent', mouse_params)

			print('✅ Right-click performed successfully!')

			# Wait for checkbox to appear
			print('⏳ Waiting for checkbox to appear...')
			await asyncio.sleep(3)

			await session.detach()

			return True

		except Exception as e:
			print(f'❌ Error right-clicking element: {e}')
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
			'url': 'https://www.samsclub.com/login',
			'timestamp': asyncio.get_event_loop().time(),
			'dom_tree': element_to_dict(self.dom_tree.root) if self.dom_tree.root else None,
		}

		filename = 'perimeterx_interaction_results.json'
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

	async def is_element_in_visible_iframe(self, element: DOMElementNode) -> bool:
		"""Check if element is under an iframe with computed style display: block by traversing up the DOM tree"""
		# Start from the element and traverse up to find an iframe parent
		current = element

		while current:
			# Check all elements to find potential iframe parents
			all_elements = self.dom_tree.get_all_elements()

			# Find elements that have current as a child
			parent_found = False
			for potential_parent in all_elements:
				if hasattr(potential_parent, 'children') and current in potential_parent.children:
					current = potential_parent
					parent_found = True

					# Check if this parent is an iframe with display: block
					if current.tag == 'iframe':
						# Check computed styles
						computed_styles = getattr(current, 'computed_styles', {})
						if computed_styles.get('display') == 'block':
							print(f'✅ Found parent iframe with display: block - node_id: {current.node_id}')
							return True
						else:
							print(f'❌ Found parent iframe but display is: {computed_styles.get("display", "unknown")}')
					break

			if not parent_found:
				# Reached root or couldn't find parent
				break

		return False

	async def run_test(self):
		"""Run the complete test"""
		try:
			print('🔬 Starting PerimeterX Interaction Test')
			print('=' * 60)

			# Setup
			await self.setup()

			# Build DOM tree
			start_time = time.time()
			await self.build_dom_tree()
			end_time = time.time()
			print(f'🌳 DOM tree built in {end_time - start_time:.2f} seconds')

			# Find "Press & Hold" element
			press_hold_elements = self.dom_tree.get_element_by_condition(
				lambda e: e.tag == 'p' and e.text_content and 'Press & Hold' in e.text_content
			)

			# Filter to only elements within visible iframes
			print(f'🔍 Found {len(press_hold_elements)} "Press & Hold" elements, checking parent iframes...')
			visible_press_hold_elements = []
			for element in press_hold_elements:
				print(f'\n📍 Checking element with text: "{element.text_content}"')
				if await self.is_element_in_visible_iframe(element):
					visible_press_hold_elements.append(element)
					print('✅ This element is under a visible iframe!')
				else:
					print('❌ This element is NOT under a visible iframe')

			press_hold_element = visible_press_hold_elements[0] if visible_press_hold_elements else None

			if press_hold_element:
				print(f'🖱️  Found "Press & Hold" element: "{press_hold_element.text_content}"')
				print(f'   Frame URL: {press_hold_element.frame_url}')

				# Right-click the element
				success = await self.click_element_with_cdp(press_hold_element)

				if success:
					print('🎉 Test PASSED! PerimeterX captcha solved successfully.')
				else:
					print('❌ Test FAILED! Could not left-click element.')

			else:
				print('❌ Test FAILED! No "Press & Hold" element found in DOM tree.')
				print('   Make sure the PerimeterX popup has appeared.')

			# Save results
			await asyncio.sleep(5)
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

	test = PerimeterXInteractionTest(use_remote_browser=USE_REMOTE_BROWSER)
	await test.run_test()


if __name__ == '__main__':
	asyncio.run(main())
