#!/usr/bin/env python3
"""
Test script for DOM enrichment functionality.
This script demonstrates how the enriched DOM tree provides visibility,
interactivity, and positioning data for elements.
"""

import asyncio
import logging

from playwright.async_api import async_playwright

from browser_use.dom.dom_optimized.service import DOMService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_dom_enrichment():
	"""Test DOM enrichment with a simple HTML page"""

	async with async_playwright() as p:
		browser = await p.chromium.launch(headless=True)
		page = await browser.new_page()

		# Create a test HTML page with various elements
		test_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                .hidden { display: none; }
                .invisible { visibility: hidden; }
                .transparent { opacity: 0; }
                .positioned { position: absolute; top: 10px; left: 10px; }
                .interactive { cursor: pointer; }
                .button { background: blue; color: white; padding: 10px; }
            </style>
        </head>
        <body>
            <div id="visible-div" class="button">Visible Button</div>
            <div id="hidden-div" class="hidden">Hidden Div</div>
            <div id="invisible-div" class="invisible">Invisible Div</div>
            <div id="transparent-div" class="transparent">Transparent Div</div>
            <div id="positioned-div" class="positioned">Positioned Div</div>
            <button id="interactive-btn" class="interactive">Interactive Button</button>
            <a href="#" id="link">Link</a>
            <input type="text" id="input" placeholder="Input field">
            <iframe src="data:text/html,<h1>Iframe Content</h1>" id="test-iframe"></iframe>
        </body>
        </html>
        """

		await page.set_content(test_html)
		await page.wait_for_load_state('networkidle')

		# Create CDP session and DOM service
		cdp_session = await page.context.new_cdp_session(page)

		dom_service = DOMService(page, cdp_session)

		# Build enriched DOM tree
		logger.info('Building enriched DOM tree...')
		dom_tree = await dom_service.build_dom_tree()

		# Test enriched functionality
		logger.info('Testing enriched DOM functionality...')

		# Get all elements
		all_elements = dom_tree.get_all_elements()
		logger.info(f'Total elements: {len(all_elements)}')

		# Test visibility detection
		visible_elements = dom_tree.get_visible_elements()
		logger.info(f'Visible elements: {len(visible_elements)}')

		# Test interactivity detection
		interactive_elements = dom_tree.get_interactive_elements()
		logger.info(f'Interactive elements: {len(interactive_elements)}')

		# Test positioned elements
		positioned_elements = dom_tree.get_positioned_elements()
		logger.info(f'Positioned elements: {len(positioned_elements)}')

		# Test elements with bounding boxes
		elements_with_bbox = dom_tree.get_elements_with_bounding_box()
		logger.info(f'Elements with bounding box: {len(elements_with_bbox)}')

		# Detailed analysis of specific elements
		logger.info('\n--- Detailed Element Analysis ---')

		for element in all_elements:
			if element.attributes.get('id'):
				element_id = element.attributes['id']
				logger.info(f'\nElement: {element_id} ({element.tag})')
				logger.info(f'  Visible: {element.is_visible}')
				logger.info(f'  Interactive: {element.is_interactive}')
				logger.info(f'  Positioned: {element.is_positioned}')

				if element.bounding_box:
					bbox = element.bounding_box
					logger.info(f'  Bounding box: x={bbox["x"]}, y={bbox["y"]}, w={bbox["width"]}, h={bbox["height"]}')

				if element.paint_order is not None:
					logger.info(f'  Paint order: {element.paint_order}')

				if element.computed_styles:
					key_styles = ['display', 'visibility', 'opacity', 'position', 'cursor']
					styles_info = {k: element.computed_styles.get(k) for k in key_styles if element.computed_styles.get(k)}
					if styles_info:
						logger.info(f'  Key styles: {styles_info}')

		await browser.close()
		logger.info('\nDOM enrichment test completed successfully!')


if __name__ == '__main__':
	asyncio.run(test_dom_enrichment())
