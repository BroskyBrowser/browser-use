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
from typing import Dict, Optional

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from playwright.async_api import CDPSession, Page, async_playwright

from browser_use.dom.dom_optimized.service import DOMService
from browser_use.dom.dom_optimized.views import DOMElementNode, DOMTextNode, DOMTree

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TurnstileInteractionTest:
	"""Test class for Turnstile checkbox interaction"""

	def __init__(self):
		self.page: Optional[Page] = None
		self.cdp_session: Optional[CDPSession] = None
		self.dom_service: Optional[DOMService] = None
		self.dom_tree: Optional[DOMTree] = None
		self.sessions: Dict[str, CDPSession] = {}

	async def setup(self):
		"""Setup browser and navigate to Turnstile page"""
		print('🚀 Setting up browser and navigating to Turnstile...')

		self.playwright = await async_playwright().start()
		self.browser = await self.playwright.chromium.launch(
			headless=False,  # Show browser for debugging
			args=['--remote-debugging-port=9222'],
		)
		self.context = await self.browser.new_context()
		self.page = await self.context.new_page()
		self.cdp_session = await self.context.new_cdp_session(self.page)

		# Navigate to Turnstile page
		#url = 'https://seleniumbase.io/apps/turnstile'
		url = 'https://ahrefs.com/backlink-checker/?input=www.he-tk.de&amp;mode=subdomains'
		print(f'🌐 Navigating to: {url}')
		await self.page.goto(url)

		# Wait for page load with longer timeout
		try:
			await self.page.wait_for_load_state('domcontentloaded', timeout=60000)
			print('📄 DOM content loaded')
		except:
			print('⚠️  DOM content load timeout, continuing anyway...')

		print('⏳ Waiting 10 seconds for Turnstile to fully load...')
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

	async def find_checkbox_in_dom(self) -> Optional[tuple]:
		"""
		Find checkbox in DOM tree and return (element, session, frame_info)
		Returns tuple of (checkbox_element, cdp_session, frame_info) or None
		"""
		print('🔍 Searching for checkbox in DOM tree...')

		async def find_checkbox_recursive(element: DOMElementNode, session: CDPSession, frame_info: str) -> Optional[tuple]:
			"""Recursively search for checkbox in element tree"""

			# Check if current element is a checkbox or clickeable element
			if element.tag == 'input' and element.attributes.get('type') == 'checkbox':
				print(f'✅ Found checkbox in {frame_info}')
				print(f'   Node ID: {getattr(element, "node_id", None)}')
				print(f'   Attributes: {element.attributes}')
				return (element, session, frame_info)

			# Also look for elements that might be Turnstile challenge elements
			if element.tag in ['div', 'span', 'button'] and any(
				keyword in str(element.attributes).lower()
				for keyword in ['turnstile', 'challenge', 'checkbox', 'verify', 'captcha']
			):
				print(f'🎯 Found potential Turnstile element in {frame_info}')
				print(f'   Tag: {element.tag}')
				print(f'   Node ID: {getattr(element, "node_id", None)}')
				print(f'   Attributes: {element.attributes}')
				return (element, session, frame_info)

			# Check if element is an iframe with content
			if element.tag == 'iframe':
				print(f'🔍 Found iframe element with {len(element.children)} children')
				# Look for iframe content marked by our DOM service
				for child in element.children:
					if isinstance(child, DOMElementNode):
						print(f'   Child: {child.tag}, attributes: {child.attributes}')
						# Check if this is iframe content
						target_id = child.attributes.get('data-target-id')
						if target_id:
							print(f'🎯 Searching in iframe content (target: {target_id})')
							# Try to get or create session for this iframe
							iframe_session = await self._get_iframe_session(target_id)
							if iframe_session:
								result = await find_checkbox_recursive(child, iframe_session, f'iframe-{target_id}')
								if result:
									return result
						else:
							# Also search in regular iframe children
							result = await find_checkbox_recursive(child, session, f'{frame_info}-iframe-child')
							if result:
								return result

			# Search in children
			for child in element.children:
				if isinstance(child, DOMElementNode):
					result = await find_checkbox_recursive(child, session, frame_info)
					if result:
						return result

			return None

		# Start search from root
		if self.dom_tree and self.dom_tree.root:
			return await find_checkbox_recursive(self.dom_tree.root, self.cdp_session, 'main-frame')

		return None

	async def _get_iframe_session(self, target_id: str) -> Optional[CDPSession]:
		"""Get or create CDP session for iframe target using Playwright's frame API"""
		try:
			if target_id in self.sessions:
				return self.sessions[target_id]

			# Find the iframe frame using Playwright's frame API (like in service.py)
			iframe_frame = None
			
			logger.debug(f'Looking for iframe with target_id: {target_id}')
			logger.debug(f'Available frames: {[f.url for f in self.page.frames]}')
			
			# Try to find the frame that corresponds to this target_id
			for frame in self.page.frames:
				if frame == self.page.main_frame:
					continue  # Skip main frame
					
				# For Turnstile, the iframe is usually one of the child frames
				# We can try to match by checking if it's not the main frame
				iframe_frame = frame
				logger.debug(f'Found potential iframe frame: {frame.url}')
				break
			
			if iframe_frame:
				logger.debug(f'Creating CDP session for iframe: {iframe_frame.url}')
				
				# Create a CDP session for this specific frame
				iframe_session = await self.context.new_cdp_session(iframe_frame)
				self.sessions[target_id] = iframe_session
				
				return iframe_session
			else:
				logger.warning(f'No matching frame found for target_id: {target_id}')
				return None

		except Exception as e:
			logger.warning(f'Error getting iframe session for {target_id}: {e}')
			import traceback
			logger.debug(traceback.format_exc())

		return None

	async def click_checkbox_with_cdp(self, checkbox_element: DOMElementNode, session: CDPSession, frame_info: str):
		"""Click checkbox using CDP commands"""
		print(f'🖱️  Attempting to click checkbox in {frame_info}...')

		try:
			node_id = getattr(checkbox_element, 'node_id', None)
			if not node_id:
				print('❌ No node ID available for checkbox')
				return False

			# Get box model for the checkbox
			print(f'📐 Getting box model for node {node_id}...')
			box_model_result = await session.send('DOM.getBoxModel', {'nodeId': node_id})

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
			'url': 'https://seleniumbase.io/apps/turnstile',
			'timestamp': asyncio.get_event_loop().time(),
			'dom_tree': element_to_dict(self.dom_tree.root) if self.dom_tree.root else None,
			'statistics': {
				'total_elements': len(self.dom_tree.get_all_elements()),
				'iframe_elements': len([e for e in self.dom_tree.get_all_elements() if e.tag == 'iframe']),
				'checkbox_elements': len(
					[e for e in self.dom_tree.get_all_elements() if e.tag == 'input' and e.attributes.get('type') == 'checkbox']
				),
			},
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
			await self.build_dom_tree()

			# Find checkbox
			checkbox_info = await self.find_checkbox_in_dom()

			if checkbox_info:
				checkbox_element, session, frame_info = checkbox_info

				# Click checkbox
				success = await self.click_checkbox_with_cdp(checkbox_element, session, frame_info)

				if success:
					print('🎉 Test PASSED! Checkbox was found and clicked successfully.')
				else:
					print('❌ Test FAILED! Could not click checkbox.')
			else:
				print('❌ Test FAILED! No checkbox found in DOM tree.')

			# Save results

			print(self.dom_tree.translate_all_to_llm(format='csv'))

			await self.save_results()

		except Exception as e:
			print(f'💥 Test failed with exception: {e}')
			logger.exception('Test exception details:')

		finally:
			await self.cleanup()


async def main():
	"""Main test function"""
	test = TurnstileInteractionTest()
	await test.run_test()


if __name__ == '__main__':
	asyncio.run(main())
