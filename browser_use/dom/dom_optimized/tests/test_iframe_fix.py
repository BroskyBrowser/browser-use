import asyncio
import json

from playwright.async_api import Browser, async_playwright

from browser_use.dom.dom_optimized.service import DOMService


async def test_iframe_fix():
	"""Test that iframe content is properly loaded without duplication"""
	async with async_playwright() as p:
		browser: Browser = await p.chromium.launch(
			headless=False,  # Show browser for debugging
			args=['--remote-debugging-port=9222'],
		)
		context = await browser.new_context()
		page = await context.new_page()
		cdp_session = await context.new_cdp_session(page)
		# Navigate to the turnstile page
		await page.goto('https://seleniumbase.io/apps/turnstile')
		await page.wait_for_load_state('load')

		# Create CDP session

		# wait enter from user


		# Create DOM service
		dom_service = DOMService(page, context, cdp_session)

		# Build DOM tree
		dom_tree = await dom_service.build_dom_tree()

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
			print(f'  frame_id: {iframe.frame_id}')
			print(f'  children: {len(iframe.children)}')

			if iframe.children:
				for j, child in enumerate(iframe.children):
					print(f'    Child {j + 1}: {child.tag if hasattr(child, "tag") else "text"} (frame_id: {child.frame_id})')
		await browser.close()

		print(dom_tree.translate_all_to_llm(format='csv'))

		# Return results
		return {
			'iframe_count': len(iframe_elements),
			'duplicate_backend_node_ids': duplicates,
			'total_backend_node_ids': len(backend_node_ids),
			'iframe_details': [
				{
					'src': iframe.attributes.get('src', 'N/A'),
					'frame_id': iframe.frame_id,
					'children_count': len(iframe.children),
					'children_frame_ids': [child.frame_id for child in iframe.children if hasattr(child, 'frame_id')],
				}
				for iframe in iframe_elements
			],
		}


if __name__ == '__main__':
	result = asyncio.run(test_iframe_fix())
	# wait 60 seconds
	
	print('\n' + '=' * 50)
	print('TEST RESULTS:')
	print(json.dumps(result, indent=2))
