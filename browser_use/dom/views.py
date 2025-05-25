from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, Optional
import json

from browser_use.dom.history_tree_processor.view import CoordinateSet, HashedDomElement, ViewportInfo
from browser_use.utils import time_execution_sync

# Avoid circular import issues
if TYPE_CHECKING:
	from .views import DOMElementNode


@dataclass(frozen=False)
class DOMBaseNode:
	is_visible: bool
	# Use None as default and set parent later to avoid circular reference issues
	parent: Optional['DOMElementNode']

	def __json__(self) -> dict:
		raise NotImplementedError('DOMBaseNode is an abstract class')


@dataclass(frozen=False)
class DOMTextNode(DOMBaseNode):
	text: str
	type: str = 'TEXT_NODE'

	def has_parent_with_highlight_index(self) -> bool:
		current = self.parent
		while current is not None:
			# stop if the element has a highlight index (will be handled separately)
			if current.highlight_index is not None:
				return True

			current = current.parent
		return False

	def is_parent_in_viewport(self) -> bool:
		if self.parent is None:
			return False
		return self.parent.is_in_viewport

	def is_parent_top_element(self) -> bool:
		if self.parent is None:
			return False
		return self.parent.is_top_element

	def __json__(self) -> dict:
		return {
			'text': self.text,
			'type': self.type,
		}


@dataclass(frozen=False)
class DOMElementNode(DOMBaseNode):
	"""
	xpath: the xpath of the element from the last root node (shadow root or iframe OR document if no shadow root or iframe).
	To properly reference the element we need to recursively switch the root node until we find the element (work you way up the tree with `.parent`)
	"""

	tag_name: str
	xpath: str
	attributes: dict[str, str]
	children: list[DOMBaseNode]
	is_interactive: bool = False
	is_top_element: bool = False
	is_in_viewport: bool = False
	shadow_root: bool = False
	highlight_index: int | None = None
	viewport_coordinates: CoordinateSet | None = None
	page_coordinates: CoordinateSet | None = None
	viewport_info: ViewportInfo | None = None

	"""
	### State injected by the browser context.

	The idea is that the clickable elements are sometimes persistent from the previous page -> tells the model which objects are new/_how_ the state has changed
	"""
	is_new: bool | None = None
	
	# New semantic fields for LLM optimization
	section: str | None = None
	include_in_llm_view: bool = True

	def compute_semantics(self) -> None:
		"""Compute semantic metadata for more efficient LLM processing."""
		# Store parent information for context
		if self.parent:
			self.parent_role = self.parent.attributes.get('role') or self.parent._infer_role_from_tag() if hasattr(self.parent, '_infer_role_from_tag') else ''
			self.parent_tag = self.parent.tag_name
		else:
			self.parent_role = None
			self.parent_tag = None
		
		# Determine if should be included in LLM view
		self.include_in_llm_view = self._should_include_in_llm_view()

	def _should_include_in_llm_view(self) -> bool:
		"""Determine if this element should be included in LLM payload."""
		# Always include highlighted/interactive elements
		if self.highlight_index is not None or self.is_interactive:
			return True
		
		# Include if visible and in viewport
		if self.is_visible and self.is_in_viewport and self.is_top_element:
			return True
		
		# Include important form elements based on parent context
		if self.parent_tag == 'form' and self.tag_name in ['input', 'button', 'select', 'textarea']:
			return True
		
		return False

	def to_llm_payload(self, selector_map: 'SelectorMap') -> str:
		"""Generate compact CSV payload for LLM with only essential columns."""
		csv_rows = []
		
		# CSV Header - only essential columns for LLM decision making
		header = "i|p|t|tx|aria|int"
		csv_rows.append(header)
		
		for node in selector_map.values():
			if not node.include_in_llm_view:
				continue
			
			# Get text content (trimmed)
			text = node.get_all_text_till_next_clickable_element(max_depth=2)
			text = text.strip()[:50] if text else ''
			# Escape | characters in text to avoid CSV conflicts
			text = text.replace('|', '¦') if text else ''
			
			# Get aria-label if it exists and is different from text
			aria_label = ''
			if 'aria-label' in node.attributes:
				aria_value = node.attributes['aria-label'].strip()
				# Only include aria-label if it's different from the text content
				if aria_value and aria_value != text.replace('¦', '|'):  # Compare with unescaped text
					aria_label = aria_value[:50]  # Limit length
					aria_label = aria_label.replace('|', '¦')  # Escape pipes
			
			# Find parent highlight_index if exists
			parent_id = ''
			if node.parent and hasattr(node.parent, 'highlight_index') and node.parent.highlight_index is not None:
				parent_id = str(node.parent.highlight_index)
			
			# Build CSV row with only essential fields
			row_data = [
				str(node.highlight_index) if node.highlight_index is not None else '',  # i - index (for actions)
				parent_id,                                                              # p - parent (hierarchy)
				node.tag_name[:3] if node.tag_name else '',                           # t - tag (element type)
				text,                                                                  # tx - text (content)
				aria_label,                                                            # aria - aria-label (when different)
				'1' if node.is_interactive else '0',                                  # int - interactive (actionable)
			]
			
			csv_rows.append('|'.join(row_data))
		
		# Sort rows by section priority, then by y-position (keeping header first)
		if len(csv_rows) > 1:
			header = csv_rows[0]
			data_rows = csv_rows[1:]
			
			# Simple sort by index to maintain consistent order
			def sort_key(row):
				fields = row.split('|')
				index = int(fields[0]) if fields[0].isdigit() else 999
				return index
			
			data_rows.sort(key=sort_key)
			csv_rows = [header] + data_rows
		
		return '\n'.join(csv_rows)

	def __json__(self) -> dict:
		return {
			'tag_name': self.tag_name,
			'xpath': self.xpath,
			'attributes': self.attributes,
			'is_visible': self.is_visible,
			'is_interactive': self.is_interactive,
			'is_top_element': self.is_top_element,
			'is_in_viewport': self.is_in_viewport,
			'shadow_root': self.shadow_root,
			'highlight_index': self.highlight_index,
			'viewport_coordinates': self.viewport_coordinates,
			'page_coordinates': self.page_coordinates,
			'children': [child.__json__() for child in self.children],
		}

	def __repr__(self) -> str:
		tag_str = f'<{self.tag_name}'

		# Add attributes
		for key, value in self.attributes.items():
			tag_str += f' {key}="{value}"'
		tag_str += '>'

		# Add extra info
		extras = []
		if self.is_interactive:
			extras.append('interactive')
		if self.is_top_element:
			extras.append('top')
		if self.shadow_root:
			extras.append('shadow-root')
		if self.highlight_index is not None:
			extras.append(f'highlight:{self.highlight_index}')
		if self.is_in_viewport:
			extras.append('in-viewport')

		if extras:
			tag_str += f' [{", ".join(extras)}]'

		return tag_str

	@cached_property
	def hash(self) -> HashedDomElement:
		from browser_use.dom.history_tree_processor.service import (
			HistoryTreeProcessor,
		)

		return HistoryTreeProcessor._hash_dom_element(self)

	def get_all_text_till_next_clickable_element(self, max_depth: int = -1) -> str:
		text_parts = []

		def collect_text(node: DOMBaseNode, current_depth: int) -> None:
			if max_depth != -1 and current_depth > max_depth:
				return

			# Skip this branch if we hit a highlighted element (except for the current node)
			if isinstance(node, DOMElementNode) and node != self and node.highlight_index is not None:
				return

			if isinstance(node, DOMTextNode):
				text_parts.append(node.text)
			elif isinstance(node, DOMElementNode):
				for child in node.children:
					collect_text(child, current_depth + 1)

		collect_text(self, 0)
		return '\n'.join(text_parts).strip()

	@time_execution_sync('--clickable_elements_to_string')
	def clickable_elements_to_string(self, include_attributes: list[str] | None = None) -> str:
		"""Convert the processed DOM content to HTML."""
		formatted_text = []

		def process_node(node: DOMBaseNode, depth: int) -> None:
			next_depth = int(depth)
			depth_str = depth * '\t'

			if isinstance(node, DOMElementNode):
				# Add element with highlight_index
				if node.highlight_index is not None:
					next_depth += 1

					text = node.get_all_text_till_next_clickable_element()
					attributes_html_str = ''
					if include_attributes:
						attributes_to_include = {
							key: str(value) for key, value in node.attributes.items() if key in include_attributes
						}

						# Easy LLM optimizations
						# if tag == role attribute, don't include it
						if node.tag_name == attributes_to_include.get('role'):
							del attributes_to_include['role']

						# if aria-label == text of the node, don't include it
						if (
							attributes_to_include.get('aria-label')
							and attributes_to_include.get('aria-label', '').strip() == text.strip()
						):
							del attributes_to_include['aria-label']

						# if placeholder == text of the node, don't include it
						if (
							attributes_to_include.get('placeholder')
							and attributes_to_include.get('placeholder', '').strip() == text.strip()
						):
							del attributes_to_include['placeholder']

						if attributes_to_include:
							# Format as key1='value1' key2='value2'
							attributes_html_str = ' '.join(f"{key}='{value}'" for key, value in attributes_to_include.items())

					# Build the line
					if node.is_new:
						highlight_indicator = f'*[{node.highlight_index}]*'
					else:
						highlight_indicator = f'[{node.highlight_index}]'

					line = f'{depth_str}{highlight_indicator}<{node.tag_name}'

					if attributes_html_str:
						line += f' {attributes_html_str}'

					if text:
						# Add space before >text only if there were NO attributes added before
						if not attributes_html_str:
							line += ' '
						line += f'>{text}'
					# Add space before /> only if neither attributes NOR text were added
					elif not attributes_html_str:
						line += ' '

					line += ' />'  # 1 token
					formatted_text.append(line)

				# Process children regardless
				for child in node.children:
					process_node(child, next_depth)

			elif isinstance(node, DOMTextNode):
				# Add text only if it doesn't have a highlighted parent
				if (
					not node.has_parent_with_highlight_index()
					and node.parent
					and node.parent.is_visible
					and node.parent.is_top_element
				):  # and node.is_parent_top_element()
					formatted_text.append(f'{depth_str}{node.text}')

		process_node(self, 0)
		return '\n'.join(formatted_text)

	@time_execution_sync('--clickable_elements_to_string_optimized')
	def clickable_elements_to_string_optimized(self, selector_map: 'SelectorMap', include_attributes: list[str] | None = None) -> str:
		"""Optimized version using flat iteration instead of recursion."""
		formatted_lines = []
		
		# Get all highlighted nodes sorted by position
		highlighted_nodes = [node for node in selector_map.values() if node.highlight_index is not None]
		highlighted_nodes.sort(key=lambda n: (n.highlight_index or 0))
		
		for node in highlighted_nodes:
			text = node.get_all_text_till_next_clickable_element()
			attributes_html_str = ''
			
			if include_attributes:
				attributes_to_include = {
					key: str(value) for key, value in node.attributes.items() if key in include_attributes
				}

				# LLM optimizations - remove redundant attributes
				if node.tag_name == attributes_to_include.get('role'):
					attributes_to_include.pop('role', None)

				if (
					attributes_to_include.get('aria-label')
					and attributes_to_include.get('aria-label', '').strip() == text.strip()
				):
					attributes_to_include.pop('aria-label', None)

				if (
					attributes_to_include.get('placeholder')
					and attributes_to_include.get('placeholder', '').strip() == text.strip()
				):
					attributes_to_include.pop('placeholder', None)

				if attributes_to_include:
					attributes_html_str = ' '.join(f"{key}='{value}'" for key, value in attributes_to_include.items())

			# Build the line
			highlight_indicator = f'*[{node.highlight_index}]*' if node.is_new else f'[{node.highlight_index}]'
			line = f'{highlight_indicator}<{node.tag_name}'

			if attributes_html_str:
				line += f' {attributes_html_str}'

			if text:
				if not attributes_html_str:
					line += ' '
				line += f'>{text}'
			elif not attributes_html_str:
				line += ' '

			line += ' />'
			formatted_lines.append(line)

		return '\n'.join(formatted_lines)


SelectorMap = dict[int, DOMElementNode]


@dataclass
class DOMState:
	"""DOM state container with optimized LLM serialization.
	
	Usage examples:
	
	# Ultra-compact CSV format (only essential columns for LLM decision making)
	csv_payload = dom_state.to_llm_payload()
	# Output: 
	# i|p|t|r|tx|aria|int
	# 1||nav|navigation|||0
	# 2|1|a|link|Home|Go to homepage|1
	# 3||for|form|||0
	# 4|3|inp|textbox||Enter your email|1
	
	# Essential CSV Columns:
	# i: index (for actions), p: parentId (hierarchy), t: tag (element type)
	# r: role (semantics), tx: text (content), aria: aria-label (when different), int: interactive (0/1)
	
	# Legacy string format (still available for debugging)
	html_output = dom_state.element_tree.clickable_elements_to_string_optimized(
		dom_state.selector_map, 
		include_attributes=['aria-label', 'placeholder']
	)
	"""
	element_tree: DOMElementNode
	selector_map: SelectorMap

	def preprocess_for_llm(self) -> None:
		"""Preprocess all nodes by computing semantics and filtering for LLM view."""
		def process_node(node: DOMBaseNode) -> None:
			if isinstance(node, DOMElementNode):
				node.compute_semantics()
				# Recursively process children
				for child in node.children:
					process_node(child)
		
		process_node(self.element_tree)

	def to_llm_payload(self) -> str:
		"""Generate optimized payload for LLM after preprocessing."""
		# Ensure semantics are computed
		self.preprocess_for_llm()
		
		# Use any node from selector_map to call the method (they all have access to the same selector_map)
		if self.selector_map:
			first_node = next(iter(self.selector_map.values()))
			return first_node.to_llm_payload(self.selector_map)
		
		return json.dumps({'n': []}, separators=(',', ':'))
