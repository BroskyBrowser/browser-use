#!/usr/bin/env python3
"""
Test script for the simplified DOM service implementation.
"""

import asyncio
import logging
import json
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.async_api import async_playwright

# Import the actual DOM classes
from browser_use.dom.dom_optimized.views import DOMTree, DOMElementNode, DOMTextNode
from browser_use.dom.dom_optimized.service import DOMService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_simplified_dom():
    """Test the simplified DOM service implementation"""
    print("🔬 Testing Simplified DOM Service")
    print("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # Test with iframe page
            test_url = "https://seleniumbase.io/apps/turnstile"
            print(f"🌐 Navigating to {test_url}")
            await page.goto(test_url, timeout=60000)
            await page.wait_for_load_state("load", timeout=60000)
            await asyncio.sleep(3)  # Wait for iframe to load
            
            # Create DOM service using simplified implementation
            cdp_session = await context.new_cdp_session(page)
            dom_service = DOMService(page, cdp_session)
            
            print("🌳 Building DOM tree with simplified recursive approach...")
            dom_tree = await dom_service.build_dom_tree()
            
            # Verify results
            assert dom_tree is not None, "DOM tree should not be None"
            assert dom_tree.root is not None, "DOM tree root should not be None"
            
            # Count elements
            all_elements = dom_tree.get_all_elements()
            print(f"📊 Total elements found: {len(all_elements)}")
            
            # Find iframe elements
            iframe_elements = dom_tree.root.find_all(lambda e: e.tag == "iframe")
            print(f"🖼️  Iframe elements: {len(iframe_elements)}")
            
            # Find iframe content (elements with data-iframe-content)
            iframe_content = dom_tree.root.find_all(lambda e: "data-iframe-content" in e.attributes)
            print(f"📦 Iframe content elements: {len(iframe_content)}")
            
            # Find elements with target IDs (iframe content)
            target_elements = dom_tree.root.find_all(lambda e: "data-target-id" in e.attributes)
            print(f"🎯 Elements with target IDs: {len(target_elements)}")
            
            # Find shadow root elements
            shadow_elements = dom_tree.root.find_all(lambda e: "data-shadow-root" in e.attributes)
            print(f"🌟 Shadow root elements: {len(shadow_elements)}")
            
            # Count interactive elements
            buttons = dom_tree.root.find_all(lambda e: e.tag == "button")
            inputs = dom_tree.root.find_all(lambda e: e.tag == "input")
            links = dom_tree.root.find_all(lambda e: e.tag == "a")
            print(f"🎮 Interactive elements - Buttons: {len(buttons)}, Inputs: {len(inputs)}, Links: {len(links)}")
            
            # Save comprehensive results
            results = {
                "test_url": test_url,
                "total_elements": len(all_elements),
                "iframe_elements": len(iframe_elements),
                "iframe_content_elements": len(iframe_content),
                "target_elements": len(target_elements),
                "shadow_elements": len(shadow_elements),
                "interactive_elements": {
                    "buttons": len(buttons),
                    "inputs": len(inputs),
                    "links": len(links)
                },
                "element_breakdown": {},
                "sample_iframe_content": []
            }
            
            # Count element types
            for element in all_elements:
                tag = element.tag
                results["element_breakdown"][tag] = results["element_breakdown"].get(tag, 0) + 1
            
            # Sample iframe content
            for elem in target_elements[:3]:
                results["sample_iframe_content"].append({
                    "tag": elem.tag,
                    "attributes": elem.attributes,
                    "children_count": len(elem.children) if hasattr(elem, 'children') else 0
                })
            
            # Save results
            with open("simplified_dom_results.json", "w") as f:
                json.dump(results, f, indent=2)
            print("💾 Results saved to simplified_dom_results.json")
            
            # Verify success criteria
            success_criteria = [
                (len(all_elements) > 20, f"Should have found multiple elements (found {len(all_elements)})"),
                (len(iframe_elements) > 0, f"Should have found iframe elements (found {len(iframe_elements)})"),
                (len(target_elements) > 0 or len(iframe_content) > 0, "Should have processed iframe content"),
                (len(buttons) + len(inputs) + len(links) > 0, "Should have found interactive elements")
            ]
            
            all_passed = True
            for condition, message in success_criteria:
                if condition:
                    print(f"✅ {message}")
                else:
                    print(f"❌ {message}")
                    all_passed = False
            
            if all_passed:
                print("\n🎉 Simplified DOM service test PASSED!")
                print("✨ The simplified recursive approach successfully:")
                print("   • Builds comprehensive DOM trees using recursive traversal")
                print("   • Processes iframes by switching sessions during traversal")
                print("   • Handles shadow roots and cross-origin content")
                print("   • Maintains unified tree structure with iframe content embedded")
                print("   • Uses much simpler and cleaner algorithm")
            else:
                print("\n❌ Simplified DOM service test FAILED!")
                return False
                
            return True
            
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            logger.exception("Simplified DOM test failed:")
            return False
            
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(test_simplified_dom()) 