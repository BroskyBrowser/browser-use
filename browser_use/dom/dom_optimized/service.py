import json
import logging
from enum import IntEnum
from typing import Any, Dict, Optional, Set

from playwright.async_api import BrowserContext, CDPSession, Page

from browser_use.dom.dom_optimized.views import DOMElementNode, DOMTextNode, DOMTree

# @file purpose: Defines DOMService for building DOM trees using raw CDP calls

logger = logging.getLogger(__name__)



class NodeType(IntEnum):
	"""CDP DOM Node Types"""

	ELEMENT = 1
	TEXT = 3
	COMMENT = 8
	DOCUMENT = 9
	DOCTYPE = 10
	DOCUMENT_FRAGMENT = 11  # Shadow root


class DOMService:
	"""˘
	Service for building DOM trees using raw Chrome DevTools Protocol (CDP) calls.
	This implementation mirrors the Go version but uses Python and Playwright's CDP interface.
	For iframe content extraction, it uses PyCDP when available to overcome Playwright's CDP session limitations.
	"""

	def __init__(self, page: Page, context: BrowserContext, cdp_session: CDPSession):
		self.page: Page = page
		self.context: BrowserContext = context
		self.cdp_session: CDPSession = cdp_session
		self.dom_tree: Optional[DOMTree] = None
		# Track backend node ID to element mapping for enrichment
		self.backend_node_map: Dict[int, DOMElementNode] = {}
		# PyCDP connection for iframe handling
		self.pycdp_connection = None
		self.cdp_port = None
		# State tracking for frame processing
		self.processed_frames: Set[str] = set()
		self.processed_iframe_nodes: Set[int] = set()
		self.sessions: Dict[str, Any] = {}

	async def set_page(self, page: Page):
		"""Set the page to work with"""
		self.page = page
		self.cdp_session = await page.context.new_cdp_session(page)

	def get_dom_tree(self) -> Optional[DOMTree]:
		"""Get the cached DOM tree or build a new one"""
		if self.dom_tree is None:
			return self.build_dom_tree()
		return self.dom_tree

	async def build_dom_tree(self) -> DOMTree:
		"""
		Build a comprehensive DOM tree including main document, iframes, and shadow roots.
		Returns a unified DOMTree with all content merged into a single tree structure.
		The tree is fully enriched with computed styles, positioning, and visibility data.
		"""
		try:
			logger.info('Starting DOM tree construction...')

			# Reset state
			self.processed_frames.clear()
			self.processed_iframe_nodes.clear()
			self.sessions.clear()
			self.backend_node_map.clear()

			# get targets and print all info
			targets_result = await self.cdp_session.send('Target.getTargets')
			target_infos = targets_result.get('targetInfos', [])
			for target in target_infos:
				logger.info(f'Target: {target}')

			# Get the main document and start recursive traversal
			doc_result = await self.cdp_session.send('DOM.getDocument', {'depth': -1, 'pierce': True})

			root_node = doc_result.get('root')
			if not root_node:
				raise ValueError('CDP did not provide root node - cannot build DOM tree without CDP data')
			else:
				# Start recursive traversal from root
				root_element = await self._traverse_node_recursive(root_node, root_node.get('frameId'))

			if root_element is None:
				raise ValueError('Failed to build DOM tree from CDP data - root element is None')

			# Create the DOM tree
			self.dom_tree = DOMTree(root_element)

			# Enrich the tree with computed styles and positioning data
			# await enrich_dom_tree(self.dom_tree, self.backend_node_map, self.sessions, self.session_frame_ids, self.cdp_session)

			logger.info('DOM tree construction and enrichment completed successfully')
			return self.dom_tree

		except Exception as e:
			logger.error(f'Error building DOM tree: {e}')
			# Re-raise the exception instead of creating fallback
			raise RuntimeError(f'Failed to build DOM tree from CDP data: {e}') from e

	async def _traverse_node_recursive(self, cdp_node: Dict[str, Any], frame_id: str) -> Optional[DOMElementNode]:
		"""
		Recursively traverse a CDP node and its children, switching to iframe sessions when needed.
		"""
		try:
			node_id = cdp_node.get('nodeId')
			# Validate that CDP provides node_id
			if node_id is None:
				raise ValueError(f'CDP did not provide node_id for node: {cdp_node}')

			# Extract all required CDP fields
			backend_node_id = cdp_node.get('backendNodeId')
			if backend_node_id is None:
				raise ValueError(f'CDP did not provide backendNodeId for node: {cdp_node}')

			node_type = NodeType(cdp_node.get('nodeType', 0))
			node_name = cdp_node.get('nodeName', '')

			# Handle different node types
			if node_type == NodeType.DOCUMENT:
				# For document nodes, process children directly
				children = cdp_node.get('children', [])
				for child in children:
					result = await self._traverse_node_recursive(child, frame_id)
					if result:
						return result
				return None

			elif node_type == NodeType.DOCTYPE:
				# Skip DOCTYPE nodes
				return None

			elif node_type == NodeType.ELEMENT:
				# Extract attributes
				attributes = {}
				attrs_list = cdp_node.get('attributes', [])
				for i in range(0, len(attrs_list), 2):
					if i + 1 < len(attrs_list):
						attributes[attrs_list[i]] = attrs_list[i + 1]

				# Create DOM element
				element = DOMElementNode(
					node_id=node_id,
					tag=node_name.lower(),
					backend_node_id=backend_node_id,
					frame_id=frame_id,
					attributes=attributes,
				)

				# Add to backend node mapping for enrichment
				self.backend_node_map[backend_node_id] = element

				# Process all children (elements, text nodes, shadow roots)
				children = cdp_node.get('children', [])
				for child in children:
					child_element = await self._traverse_node_recursive(child, frame_id)
					if child_element:
						element.append_child(child_element)
						# If it's a text node, aggregate its text to parent's text_content
						if isinstance(child_element, DOMTextNode):
							element.text_content += ' ' + child_element.text if element.text_content else child_element.text

				# Process shadow roots - they can appear as a separate property
				# Shadow roots are DOCUMENT_FRAGMENT nodes, we process their children directly
				shadow_roots = cdp_node.get('shadowRoots', [])
				for shadow_root in shadow_roots:
					if shadow_root.get('nodeType') == NodeType.DOCUMENT_FRAGMENT:
						# Process shadow root children directly into this element
						shadow_children = shadow_root.get('children', [])
						for shadow_child in shadow_children:
							child_element = await self._traverse_node_recursive(shadow_child, frame_id)
							if child_element:
								element.append_child(child_element)
					else:
						# If it's not a document fragment, process normally
						shadow_element = await self._traverse_node_recursive(shadow_root, frame_id)
						if shadow_element:
							element.append_child(shadow_element)

				# Special handling for iframe elements
				if element.tag == 'iframe':
					logger.debug(
						f'Found iframe element: src={element.attributes.get("src", "")}, backend_node_id={backend_node_id}'
					)
					# Check if this iframe node has already been processed
					iframe_frame_id = cdp_node.get('frameId')
					child_node = await self._process_iframe_content(element, iframe_frame_id)
					if child_node:
						element.append_child(child_node)

				return element

			elif node_type == NodeType.DOCUMENT_FRAGMENT:
				# Document fragments only appear as shadow roots in the shadowRoots array
				# They should never be traversed directly through normal recursion
				logger.error(f'Unexpected DOCUMENT_FRAGMENT in normal traversal: node_id={node_id}')
				return None

			elif node_type == NodeType.TEXT:
				# Handle text nodes directly
				text_value = cdp_node.get('nodeValue', '')
				if text_value and text_value.strip():
					return DOMTextNode(
						node_id=node_id, text=text_value.strip(), backend_node_id=backend_node_id, frame_id=frame_id
					)
				return None

			elif node_type == NodeType.COMMENT:
				# Skip comment nodes
				return None

			else:
				logger.debug(f'Unhandled node type {node_type}: {node_name}')
				return None

		except Exception as e:
			logger.error(f'Error traversing node: {e}')
			return None

	async def _process_iframe_content(self, iframe_element: DOMElementNode, frame_id: str):
		"""
		Process iframe content using Playwright CDP session with proper target management.
		Returns the root HTML element of the iframe content.
		"""
		if not frame_id or frame_id in self.processed_frames:
			return
			
		self.processed_frames.add(frame_id)
		
		try:
			return await self._process_iframe_with_playwright_cdp(iframe_element, frame_id)
				
		except Exception as e:
			logger.warning(f'Error processing iframe content for frame {frame_id}: {e}')


	async def _process_iframe_with_playwright_cdp(self, iframe_element: DOMElementNode, frame_id: str):
		"""Process iframe content using Playwright's frame API and CDP"""
		try:
			# Find the iframe frame using Playwright's frame API
			iframe_frame = None
			iframe_src = iframe_element.attributes.get('src', '')
			
			logger.debug(f'Looking for iframe frame with frame_id: {frame_id}, src: {iframe_src}')
			logger.debug(f'Available frames: {[f.url for f in self.page.frames]}')
			
			# Try multiple matching strategies
			for frame in self.page.frames:
				# Strategy 1: Match by URL
				if iframe_src and iframe_src in frame.url:
					iframe_frame = frame
					logger.debug(f'Matched iframe by URL: {frame.url}')
					break
				
				# Strategy 2: Match by frame name or ID (if available)
				try:
					frame_name = await frame.get_attribute('iframe', 'name') if frame != self.page.main_frame else None
					if frame_name and frame_name in iframe_element.attributes.values():
						iframe_frame = frame
						logger.debug(f'Matched iframe by name: {frame_name}')
						break
				except:
					pass
			
			# If we still haven't found the frame, try the main frame's child frames
			if not iframe_frame and len(self.page.frames) > 1:
				# Often the iframe is the second frame (after main frame)
				for frame in self.page.frames[1:]:  # Skip main frame
					if frame.url != 'about:blank' or iframe_src == 'about:blank':
						iframe_frame = frame
						logger.debug(f'Using frame as fallback: {frame.url}')
						break
			
			if iframe_frame:
				logger.debug(f'Processing iframe frame: {iframe_frame.url}')
				
				# Create a CDP session for this specific frame
				frame_cdp_session = await self.context.new_cdp_session(iframe_frame)
				
				try:
					# Get the frame document
					frame_doc_result = await frame_cdp_session.send('DOM.getDocument', {
						'depth': -1, 
						'pierce': True
					})
					
					root = frame_doc_result.get('root')
					if root:
						logger.debug(f'Got iframe document: {root.get("documentURL", "unknown")}')
						return await self._traverse_node_recursive(root, frame_id)
					else:
						logger.warning(f'No root node in iframe document')
				
				finally:
					# Clean up the frame CDP session
					await frame_cdp_session.detach()
			else:
				logger.debug(f'No matching frame found for iframe with frame_id: {frame_id}')

		except Exception as e:
			logger.warning(f'Error processing iframe with Playwright: {e}')
			import traceback
			logger.debug(traceback.format_exc())
