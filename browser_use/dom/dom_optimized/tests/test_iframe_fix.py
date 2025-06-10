import asyncio
import json
import logging
import time

from playwright.async_api import Browser, async_playwright

from browser_use.dom.dom_optimized.service import DOMService
from browser_use.dom.dom_optimized.utils.highlight import highlight_element

# Configure logging to see debug messages
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def test_iframe_fix():
	"""Test that iframe content is properly loaded without duplication"""
	async with async_playwright() as p:
		browser: Browser = await p.chromium.launch(
			headless=False,  # Show browser for debugging
			args=[
				'--remote-debugging-port=9222',
				'--disable-blink-features=AutomationControlled',
			],
			channel='chrome',
		)
		context = await browser.new_context(
				viewport={'width': 1920, 'height': 1080},
				user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
			)
		page = await context.new_page()

		try:
			cdp_session = await context.new_cdp_session(page)
			# Navigate to the turnstile page
			url = 'https://ahrefs.com/backlink-checker/?input=www.he-tk.de&amp;mode=subdomains'
			# url = 'https://abrahamjuliot.github.io/creepjs/'
			# url = 'https://seleniumbase.io/apps/turnstile'
			# url = 'https://www.google.com'
			#url = 'https://moja.posta.si/poslji-paket'
			logger.info(f'Navigating to {url}')
			await page.goto(url)
			await page.wait_for_load_state('load')

			# Wait a bit for dynamic content
			await asyncio.sleep(2)

			# Create DOM service
			dom_service = DOMService(page, context, cdp_session)

			# Build DOM tree with overall timeout
			logger.info('Building DOM tree...')
			try:
				dom_tree = await asyncio.wait_for(
					dom_service.build_dom_tree(),
					timeout=30.0,  # 30 second overall timeout
				)
			except TimeoutError:
				logger.error('Timeout building DOM tree after 30 seconds')
				raise

			# Find iframe elements
			iframe_elements = []

			def find_iframes(element):
				if hasattr(element, 'tag') and element.tag == 'iframe':
					iframe_elements.append(element)
				if hasattr(element, 'children'):
					for child in element.children:
						find_iframes(child)

			find_iframes(dom_tree.root)

			print(f'Found {len(iframe_elements)} iframe elements')

			# Check for duplicate backend_node_ids
			backend_node_ids = set()
			duplicates = []

			def check_duplicates(element):
				if hasattr(element, 'backend_node_id'):
					if element.backend_node_id in backend_node_ids:
						duplicates.append(element.backend_node_id)
					else:
						backend_node_ids.add(element.backend_node_id)
				if hasattr(element, 'children'):
					for child in element.children:
						check_duplicates(child)

			check_duplicates(dom_tree.root)

			print(f'Total unique backend_node_ids: {len(backend_node_ids)}')
			print(f'Duplicate backend_node_ids: {duplicates}')

			# Check iframe content
			for i, iframe in enumerate(iframe_elements):
				print(f'\nIframe {i + 1}:')
				print(f'  src: {iframe.attributes.get("src", "N/A")}')
				print(f'  frame_id: {iframe.frame_url}')
				print(f'  children: {len(iframe.children)}')

				if iframe.children:
					for j, child in enumerate(iframe.children[:5]):  # Limit to first 5 children
						print(
							f'    Child {j + 1}: {child.tag if hasattr(child, "tag") else "text"} (frame_id: {child.frame_url})'
						)

			# Only print CSV if not too large
			csv_output = dom_tree.translate_interactive_to_llm(format='csv')
			print(csv_output)

			start_time = time.time()
			interactive_elements = dom_tree.get_interactive_elements()
			for element in interactive_elements:
				await highlight_element(element, page)

			end_time = time.time()
			print(f'Time taken to highlight interactive elements: {end_time - start_time} seconds')

			# wait for 10 seconds
			await asyncio.sleep(40)

			# Return results
			return {
				'iframe_count': len(iframe_elements),
				'duplicate_backend_node_ids': duplicates,
				'total_backend_node_ids': len(backend_node_ids),
				'iframe_details': [
					{
						'src': iframe.attributes.get('src', 'N/A'),
						'frame_url': iframe.frame_url,
						'children_count': len(iframe.children),
						'children_frame_urls': [child.frame_url for child in iframe.children if hasattr(child, 'frame_url')],
					}
					for iframe in iframe_elements
				],
			}

		finally:
			await browser.close()


if __name__ == '__main__':
	try:
		result = asyncio.run(test_iframe_fix())
		print('\n' + '=' * 50)
		print('TEST RESULTS:')
		print(json.dumps(result, indent=2))
	except Exception as e:
		logger.error(f'Test failed: {e}')
		import traceback

		traceback.print_exc()
