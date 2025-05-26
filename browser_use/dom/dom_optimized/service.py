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
	DOCUMENT = 9
	DOCTYPE = 10
	DOCUMENT_FRAGMENT = 11  # Shadow root


class DOMService:
	"""˘
	Service for building DOM trees using raw Chrome DevTools Protocol (CDP) calls.
	This implementation mirrors the Go version but uses Python and Playwright's CDP interface.
	"""

	def __init__(self, page: Page, context: BrowserContext, cdp_session: CDPSession):
		self.page: Page = page
		self.context: BrowserContext = context
		self.cdp_session: CDPSession = cdp_session
		self.dom_tree: Optional[DOMTree] = None
		# Track processed frames to avoid infinite loops
		self.processed_frames: Set[str] = set()
		# Track processed iframe backend_node_ids to avoid duplicates
		self.processed_iframe_nodes: Set[int] = set()
		# Track all CDP sessions for cleanup
		self.sessions: Dict[str, CDPSession] = {}
		# Track backend node ID to element mapping for enrichment
		self.backend_node_map: Dict[int, DOMElementNode] = {}

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
					if child.get('nodeType') == NodeType.ELEMENT:
						return await self._traverse_node_recursive(child, frame_id)
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

				# Process text content
				node_value = cdp_node.get('nodeValue', '')
				if node_value and node_value.strip():
					element.text_content = node_value.strip()

				# Process all children (elements, text nodes, shadow roots)
				children = cdp_node.get('children', [])
				for child in children:
					child_element = await self._traverse_node_recursive(child, frame_id)
					if child_element:
						element.append_child(child_element)

				# Process shadow roots directly
				shadow_roots = cdp_node.get('shadowRoots', [])
				for shadow_root in shadow_roots:
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
					await self._process_iframe_content(element, iframe_frame_id)

				return element

			elif node_type == NodeType.DOCUMENT_FRAGMENT:
				# Process shadow root children directly like a document
				children = cdp_node.get('children', [])
				for child in children:
					if child.get('nodeType') == NodeType.ELEMENT:
						return await self._traverse_node_recursive(child, frame_id)
				return None

			elif node_type == NodeType.TEXT:
				# Handle text nodes directly
				text_value = cdp_node.get('nodeValue', '')
				if text_value and text_value.strip():
					return DOMTextNode(
						node_id=node_id, text=text_value.strip(), backend_node_id=backend_node_id, frame_id=frame_id
					)
				return None

			else:
				logger.debug(f'Unhandled node type {node_type}: {node_name}')
				return None

		except Exception as e:
			logger.error(f'Error traversing node: {e}')
			return None

	async def _process_iframe_content(self, iframe_element: DOMElementNode, frame_id: str):
		"""
		Process iframe content by creating a dedicated CDP session for the iframe target.
		"""
		try:
			# Skip if frame_id is None or already processed
			if not frame_id or frame_id in self.processed_frames:
				return

			self.processed_frames.add(frame_id)

			# Attach to the iframe target
			attach_result = await self.cdp_session.send('Target.attachToTarget', {'targetId': frame_id, 'flatten': False})
			session_id = attach_result.get('sessionId')

			if not session_id:
				logger.warning(f'Failed to attach to iframe target: {frame_id}')
				return

			logger.debug(f'Attached to iframe with session ID: {session_id}')

			# Send DOM.getDocument command to the iframe session
			params = {'sessionId': session_id, 'method': 'DOM.getDocument', 'params': {'depth': -1, 'pierce': False}}

			# Use Target.sendMessageToTarget to communicate with the iframe session
			response = await self.cdp_session.send(
				'Target.sendMessageToTarget',
				{
					'sessionId': session_id,
					'message': json.dumps({'id': 1, 'method': 'DOM.getDocument', 'params': {'depth': -1, 'pierce': True}}),
				},
			)

			# Parse the response if it's a string
			if response and isinstance(response, str):
				try:
					response_data = json.loads(response)
					dom = response_data.get('result', {})
				except json.JSONDecodeError:
					logger.warning('Failed to parse iframe DOM response')
					return
			else:
				# Alternative approach: Try to get iframe document directly
				logger.debug('Using alternative approach to get iframe content')
				# Store the session for potential cleanup
				self.sessions[frame_id] = session_id
				return  # Skip iframe processing for now if the primary method fails

			if not dom:
				logger.warning(f'No DOM response for iframe: {frame_id}')
				return

			root = dom.get('root')
			if not root:
				logger.warning('No root node in iframe DOM response')
				return

			logger.debug(f'Processing iframe document: {root.get("documentURL", "unknown")}')

			# Process the iframe content recursively
			iframe_content = await self._traverse_node_recursive(root, frame_id)
			if iframe_content:
				iframe_element.append_child(iframe_content)
				logger.debug(f'Successfully processed iframe content for frame: {frame_id}')

		except Exception as e:
			logger.warning(f'Error processing iframe content: {e}')

	async def _get_iframe_session(self, target_id: str) -> Optional[CDPSession]:
		"""Get or create CDP session for iframe target"""
		try:
			# Attach to target
			attach_result = await self.cdp_session.send(
				'Target.attachToTarget',
				{'targetId': target_id, 'flatten': True},
			)
			session_id = attach_result.get('sessionId')

			if session_id:
				# Create new CDP session for this iframe
				iframe_session = await self.context.new_cdp_session(self.page)
				return iframe_session

		except Exception as e:
			logger.warning(f'Error getting iframe session for {target_id}: {e}')
		return None
