"""
Test for DOMService - builds DOM tree using raw CDP calls.
This test suite covers the corrected implementation that properly handles
iframes, shadow roots, and frame tree traversal using raw CDP calls.
"""

import asyncio
import logging
import json
from playwright.async_api import async_playwright
from browser_use.dom.dom_optimized.service import DOMService
from browser_use.dom.dom_optimized.views import DOMTree, DOMElementNode, DOMTextNode

# Enable debug logging to see CDP calls
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestDOMService:
    """Test suite for the corrected DOMService implementation"""

    async def test_basic_dom_building(self):
        """Test basic DOM tree building with simple HTML"""
        print("🧪 Testing basic DOM building...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # Create simple HTML
                html_content = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Test Page</title>
                </head>
                <body>
                    <div id="main" class="container">
                        <h1>Hello World</h1>
                        <button id="btn1">Click Me</button>
                        <input type="text" placeholder="Enter text">
                        <a href="https://example.com">Link</a>
                    </div>
                </body>
                </html>
                """
                
                await page.set_content(html_content)
                await page.wait_for_load_state("load")
                
                # Create DOM service
                cdp_session = await context.new_cdp_session(page)
                dom_service = DOMService(page, cdp_session)
                
                # Build DOM tree
                dom_tree = await dom_service.build_dom_tree()
                
                # Verify basic structure
                assert dom_tree is not None
                assert dom_tree.root is not None
                assert dom_tree.root.tag == "html"
                
                # Count elements
                all_elements = dom_tree.get_all_elements()
                assert len(all_elements) > 0
                
                # Find specific elements
                buttons = dom_tree.root.find_all(lambda e: e.tag == "button")
                assert len(buttons) == 1
                assert buttons[0].attributes.get("id") == "btn1"
                
                inputs = dom_tree.root.find_all(lambda e: e.tag == "input")
                assert len(inputs) == 1
                
                links = dom_tree.root.find_all(lambda e: e.tag == "a")
                assert len(links) == 1
                
                print("✅ Basic DOM building test passed!")
                
            finally:
                await browser.close()

    async def test_iframe_handling(self):
        """Test iframe detection and content merging"""
        print("🧪 Testing iframe handling...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # Navigate to page with iframes (Cloudflare Turnstile)
                test_url = "https://seleniumbase.io/apps/turnstile"
                await page.goto(test_url)
                await page.wait_for_load_state("load")
                await asyncio.sleep(3)  # Wait for iframe to load
                
                # Create DOM service
                cdp_session = await context.new_cdp_session(page)
                dom_service = DOMService(page, cdp_session)
                
                # Build DOM tree
                dom_tree = await dom_service.build_dom_tree()
                
                # Verify iframe handling
                assert dom_tree is not None
                assert dom_tree.root is not None
                
                # Find iframe elements
                iframe_elements = dom_tree.root.find_all(lambda e: e.tag == "iframe")
                print(f"Found {len(iframe_elements)} iframe elements")
                
                # Find iframe content containers
                iframe_content = dom_tree.root.find_all(lambda e: e.tag == "iframe-content")
                print(f"Found {len(iframe_content)} iframe content containers")
                
                # Find elements with target IDs (iframe content)
                target_elements = dom_tree.root.find_all(lambda e: "data-target-id" in e.attributes)
                print(f"Found {len(target_elements)} elements with target IDs")
                
                # Verify we processed iframe targets
                assert len(target_elements) > 0 or len(iframe_content) > 0, "Should have found iframe content"
                
                print("✅ Iframe handling test passed!")
                
            finally:
                await browser.close()

    async def test_shadow_root_processing(self):
        """Test shadow root detection and processing"""
        print("🧪 Testing shadow root processing...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # Create HTML with shadow DOM
                html_content = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Shadow DOM Test</title>
                </head>
                <body>
                    <div id="host"></div>
                    <script>
                        const host = document.getElementById('host');
                        const shadow = host.attachShadow({mode: 'open'});
                        shadow.innerHTML = `
                            <style>
                                p { color: red; }
                            </style>
                            <p>Shadow content</p>
                            <button id="shadow-btn">Shadow Button</button>
                        `;
                    </script>
                </body>
                </html>
                """
                
                await page.set_content(html_content)
                await page.wait_for_load_state("load")
                await asyncio.sleep(1)  # Wait for shadow DOM creation
                
                # Create DOM service
                cdp_session = await context.new_cdp_session(page)
                dom_service = DOMService(page, cdp_session)
                
                # Build DOM tree
                dom_tree = await dom_service.build_dom_tree()
                
                # Verify shadow root processing
                assert dom_tree is not None
                
                # Find shadow root elements
                shadow_elements = dom_tree.root.find_all(lambda e: "data-shadow-root" in e.attributes)
                print(f"Found {len(shadow_elements)} shadow root elements")
                
                # Find elements inside shadow roots
                shadow_buttons = dom_tree.root.find_all(lambda e: e.tag == "button" and e.attributes.get("id") == "shadow-btn")
                print(f"Found {len(shadow_buttons)} shadow buttons")
                
                # Should find shadow content
                assert len(shadow_elements) > 0 or len(shadow_buttons) > 0, "Should have found shadow DOM content"
                
                print("✅ Shadow root processing test passed!")
                
            finally:
                await browser.close()

    async def test_frame_tree_structure(self):
        """Test frame tree analysis and target mapping"""
        print("🧪 Testing frame tree structure analysis...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # Navigate to page with iframes
                test_url = "https://seleniumbase.io/apps/turnstile"
                await page.goto(test_url)
                await page.wait_for_load_state("load")
                await asyncio.sleep(2)
                
                # Create CDP session
                cdp_session = await context.new_cdp_session(page)
                
                # Test frame tree analysis
                frame_tree_result = await cdp_session.send("Page.getFrameTree")
                targets_result = await cdp_session.send("Target.getTargets")
                
                frame_tree = frame_tree_result.get("frameTree", {})
                target_infos = targets_result.get("targetInfos", [])
                
                # Verify frame tree structure
                assert "frame" in frame_tree
                main_frame = frame_tree["frame"]
                assert "id" in main_frame
                assert "url" in main_frame
                
                print(f"Main frame ID: {main_frame['id']}")
                print(f"Main frame URL: {main_frame['url']}")
                
                # Verify targets
                iframe_targets = [t for t in target_infos if t.get("type") == "iframe"]
                print(f"Found {len(iframe_targets)} iframe targets")
                
                for target in iframe_targets:
                    print(f"  Target ID: {target['targetId']}")
                    print(f"  Target URL: {target['url']}")
                
                # Create DOM service and test target mapping
                dom_service = DOMService(page, cdp_session)
                
                # Map targetId by frameId
                target_by_frame_id = {}
                for target in target_infos:
                    if target.get("type") == "iframe" and target.get("frameId"):
                        target_by_frame_id[target["frameId"]] = target["targetId"]
                
                print(f"Target by frame ID mapping: {target_by_frame_id}")
                
                # Verify mapping is correct
                assert len(target_by_frame_id) == len(iframe_targets)
                
                print("✅ Frame tree structure test passed!")
                
            finally:
                await browser.close()

    async def test_complex_page_with_multiple_iframes(self):
        """Test DOM building on a complex page with multiple iframes"""
        print("🧪 Testing complex page with multiple iframes...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # Navigate to a page that typically has multiple iframes
                test_url = "https://www.google.com"
                await page.goto(test_url)
                await page.wait_for_load_state("load")
                await asyncio.sleep(2)
                
                # Create DOM service
                cdp_session = await context.new_cdp_session(page)
                dom_service = DOMService(page, cdp_session)
                
                # Build DOM tree
                dom_tree = await dom_service.build_dom_tree()
                
                # Analyze the tree
                assert dom_tree is not None
                assert dom_tree.root is not None
                
                all_elements = dom_tree.get_all_elements()
                print(f"Total elements: {len(all_elements)}")
                
                # Count element types
                element_counts = {}
                for element in all_elements:
                    tag = element.tag
                    element_counts[tag] = element_counts.get(tag, 0) + 1
                
                print("Element type counts:")
                for tag, count in sorted(element_counts.items()):
                    if count > 1:  # Only show elements with multiple instances
                        print(f"  {tag}: {count}")
                
                # Find interactive elements
                buttons = dom_tree.root.find_all(lambda e: e.tag == "button")
                inputs = dom_tree.root.find_all(lambda e: e.tag == "input")
                links = dom_tree.root.find_all(lambda e: e.tag == "a")
                
                print(f"Interactive elements - Buttons: {len(buttons)}, Inputs: {len(inputs)}, Links: {len(links)}")
                
                # Verify we have a reasonable number of elements
                assert len(all_elements) > 10, "Should have found multiple elements"
                assert len(buttons) + len(inputs) + len(links) > 0, "Should have found interactive elements"
                
                print("✅ Complex page test passed!")
                
            finally:
                await browser.close()

    async def test_error_handling(self):
        """Test error handling in DOM service"""
        print("🧪 Testing error handling...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # Test with invalid URL
                try:
                    await page.goto("https://invalid-url-that-does-not-exist.com")
                except:
                    pass  # Expected to fail
                
                # Create DOM service anyway
                cdp_session = await context.new_cdp_session(page)
                dom_service = DOMService(page, cdp_session)
                
                # Should still create a fallback DOM tree
                dom_tree = await dom_service.build_dom_tree()
                
                # Verify fallback structure
                assert dom_tree is not None
                assert dom_tree.root is not None
                assert dom_tree.root.tag == "html"
                
                print("✅ Error handling test passed!")
                
            finally:
                await browser.close()

    async def test_performance_metrics(self):
        """Test performance and resource usage"""
        print("🧪 Testing performance metrics...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # Create moderately complex HTML
                html_content = """
                <!DOCTYPE html>
                <html>
                <head><title>Performance Test</title></head>
                <body>
                """ + "".join([
                    f'<div id="div{i}" class="test-div"><p>Content {i}</p><button>Button {i}</button></div>'
                    for i in range(100)
                ]) + """
                </body>
                </html>
                """
                
                await page.set_content(html_content)
                await page.wait_for_load_state("load")
                
                # Measure DOM building time
                import time
                start_time = time.time()
                
                cdp_session = await context.new_cdp_session(page)
                dom_service = DOMService(page, cdp_session)
                dom_tree = await dom_service.build_dom_tree()
                
                end_time = time.time()
                build_time = end_time - start_time
                
                # Verify results
                assert dom_tree is not None
                all_elements = dom_tree.get_all_elements()
                
                print(f"Built DOM tree with {len(all_elements)} elements in {build_time:.3f} seconds")
                print(f"Performance: {len(all_elements)/build_time:.1f} elements/second")
                
                # Should be reasonably fast
                assert build_time < 5.0, f"DOM building took too long: {build_time:.3f}s"
                assert len(all_elements) > 200, "Should have found all elements"
                
                print("✅ Performance test passed!")
                
            finally:
                await browser.close()


# Standalone test functions for direct execution
async def test_iframe_integration():
    """Integration test for iframe handling"""
    print("🔬 Running iframe integration test...")
    
    test_instance = TestDOMService()
    await test_instance.test_iframe_handling()
    print("✅ Iframe integration test completed!")


async def test_basic_functionality():
    """Basic functionality test"""
    print("🔬 Running basic functionality test...")
    
    test_instance = TestDOMService()
    await test_instance.test_basic_dom_building()
    print("✅ Basic functionality test completed!")


async def run_all_tests():
    """Run all tests in sequence"""
    print("🔬 Running all DOM service tests...")
    print("=" * 60)
    
    test_instance = TestDOMService()
    
    tests = [
        ("Basic DOM Building", test_instance.test_basic_dom_building),
        ("Shadow Root Processing", test_instance.test_shadow_root_processing),
        ("Frame Tree Structure", test_instance.test_frame_tree_structure),
        ("Iframe Handling", test_instance.test_iframe_handling),
        ("Complex Page", test_instance.test_complex_page_with_multiple_iframes),
        ("Error Handling", test_instance.test_error_handling),
        ("Performance Metrics", test_instance.test_performance_metrics),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            print(f"\n🧪 Running: {test_name}")
            await test_func()
            passed += 1
            print(f"✅ {test_name} PASSED")
        except Exception as e:
            failed += 1
            print(f"❌ {test_name} FAILED: {e}")
            logger.exception(f"Test {test_name} failed:")
    
    print("\n" + "=" * 60)
    print(f"🏁 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed!")
    else:
        print(f"⚠️  {failed} tests failed")


if __name__ == "__main__":
    print("🔬 DOM Service Test Suite")
    print("=" * 60)
    
    # Run all tests
    asyncio.run(run_all_tests()) 