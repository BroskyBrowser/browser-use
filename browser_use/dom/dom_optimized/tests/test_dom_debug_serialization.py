"""
Test for DOM tree debug serialization functionality.
This test creates a DOM tree from a real webpage and serializes it to JSON for debugging.
"""

import asyncio
import json
import logging
from pathlib import Path

from playwright.async_api import async_playwright

from browser_use.dom.dom_optimized.service import DOMService
from browser_use.dom.dom_optimized.utils.enrichment import serialize_dom_tree_debug

# Enable debug logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestDOMDebugSerialization:
	"""Test suite for DOM tree debug serialization"""

	async def test_serialize_simple_page(self):
		"""Test serialization with a simple HTML page"""
		print('🧪 Testing DOM serialization with simple page...')

		async with async_playwright() as p:
			browser = await p.chromium.launch(headless=True)
			context = await browser.new_context()
			page = await context.new_page()

			try:
				# Create simple HTML with various elements
				html_content = """
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <title>Debug Test Page</title>
                    <style>
                        .container { padding: 20px; }
                        .hidden { display: none; }
                        .visible { display: block; color: blue; }
                    </style>
                </head>
                <body>
                    <div id="main" class="container">
                        <h1 class="visible">Debug Test</h1>
                        <p>This is a test paragraph with <strong>bold text</strong>.</p>
                        <button id="btn1" onclick="alert('clicked')">Click Me</button>
                        <input type="text" placeholder="Enter text" value="test value">
                        <a href="https://example.com" target="_blank">External Link</a>
                        <div class="hidden">Hidden content</div>
                        <ul>
                            <li>Item 1</li>
                            <li>Item 2</li>
                            <li>Item 3</li>
                        </ul>
                        <form>
                            <label for="email">Email:</label>
                            <input type="email" id="email" name="email">
                            <textarea placeholder="Comments"></textarea>
                            <select name="country">
                                <option value="us">United States</option>
                                <option value="es">Spain</option>
                            </select>
                        </form>
                    </div>
                </body>
                </html>
                """

				await page.set_content(html_content)
				await page.wait_for_load_state('load')

				# Create DOM service and build tree
				cdp_session = await context.new_cdp_session(page)
				dom_service = DOMService(page, cdp_session)
				dom_tree = await dom_service.build_dom_tree()

				# Serialize the DOM tree
				serialized_tree = serialize_dom_tree_debug(dom_tree)

				# Verify serialization structure
				assert serialized_tree['type'] == 'dom_tree'
				assert 'timestamp' in serialized_tree
				assert 'root' in serialized_tree
				assert 'stats' in serialized_tree

				# Verify stats
				stats = serialized_tree['stats']
				assert stats['total_elements'] > 0
				assert 'visible_elements' in stats
				assert 'interactive_elements' in stats
				assert 'elements_with_bounding_box' in stats

				# Verify root element
				root = serialized_tree['root']
				assert root['tag'] == 'html'
				assert 'children' in root
				assert len(root['children']) > 0

				# Save to JSON file
				test_dir = Path(__file__).parent
				output_file = test_dir / 'simple_page_dom_debug.json'

				with open(output_file, 'w', encoding='utf-8') as f:
					json.dump(serialized_tree, f, indent=2, ensure_ascii=False)

				print(f'✅ Simple page serialization test passed! Saved to {output_file}')
				print(f'📊 Stats: {stats}')

			finally:
				await browser.close()

	async def test_serialize_real_website(self):
		"""Test serialization with a real website"""
		print('🧪 Testing DOM serialization with real website...')

		async with async_playwright() as p:
			browser = await p.chromium.launch(headless=True)
			context = await browser.new_context()
			page = await context.new_page()

			try:
				# Navigate to a real website
				test_url = 'https://example.com'
				await page.goto(test_url)
				await page.wait_for_load_state('load')
				await asyncio.sleep(2)  # Wait for any dynamic content

				# Create DOM service and build tree
				cdp_session = await context.new_cdp_session(page)
				dom_service = DOMService(page, cdp_session)
				dom_tree = await dom_service.build_dom_tree()

				# Serialize the DOM tree
				serialized_tree = serialize_dom_tree_debug(dom_tree)

				# Verify serialization
				assert serialized_tree['type'] == 'dom_tree'
				assert serialized_tree['stats']['total_elements'] > 0

				# Save to JSON file
				test_dir = Path(__file__).parent
				output_file = test_dir / 'example_com_dom_debug.json'

				with open(output_file, 'w', encoding='utf-8') as f:
					json.dump(serialized_tree, f, indent=2, ensure_ascii=False)

				stats = serialized_tree['stats']
				print(f'✅ Real website serialization test passed! Saved to {output_file}')
				print(f'📊 Stats: {stats}')

			finally:
				await browser.close()

	async def test_serialize_complex_page_with_iframes(self):
		"""Test serialization with a page containing iframes"""
		print('🧪 Testing DOM serialization with iframes...')

		async with async_playwright() as p:
			browser = await p.chromium.launch(headless=False)
			context = await browser.new_context()
			page = await context.new_page()

			try:
				# Navigate to page with iframes
				test_url = 'https://seleniumbase.io/apps/turnstile'
				await page.goto(test_url)
				await page.wait_for_load_state('load')
				await asyncio.sleep(5)  # Wait for iframe content to load

				# Create DOM service and build tree
				cdp_session = await context.new_cdp_session(page)
				dom_service = DOMService(page, cdp_session)
				dom_tree = await dom_service.build_dom_tree()

				# Serialize the DOM tree
				serialized_tree = serialize_dom_tree_debug(dom_tree)

				# Verify serialization
				assert serialized_tree['type'] == 'dom_tree'
				assert serialized_tree['stats']['total_elements'] > 0

				# Save to JSON file
				test_dir = Path(__file__).parent
				output_file = test_dir / 'turnstile_page_dom_debug.json'

				with open(output_file, 'w', encoding='utf-8') as f:
					json.dump(serialized_tree, f, indent=2, ensure_ascii=False)

				stats = serialized_tree['stats']
				print(f'✅ Complex page with iframes serialization test passed! Saved to {output_file}')
				print(f'📊 Stats: {stats}')

				# Look for iframe elements in the serialized data
				def count_iframes(element):
					count = 0
					if element.get('tag') == 'iframe':
						count += 1
					for child in element.get('children', []):
						if child.get('tag'):  # Only count element children, not text nodes
							count += count_iframes(child)
					return count

				iframe_count = count_iframes(serialized_tree['root'])
				print(f'🔍 Found {iframe_count} iframe elements in serialized tree')

			finally:
				await browser.close()


async def run_debug_serialization_tests():
	"""Run all debug serialization tests"""
	test_suite = TestDOMDebugSerialization()

	print('🚀 Starting DOM debug serialization tests...')

	try:
		await test_suite.test_serialize_simple_page()
		await test_suite.test_serialize_real_website()
		await test_suite.test_serialize_complex_page_with_iframes()

		print('🎉 All DOM debug serialization tests passed!')

	except Exception as e:
		print(f'❌ Test failed: {e}')
		raise


if __name__ == '__main__':
	asyncio.run(run_debug_serialization_tests())
