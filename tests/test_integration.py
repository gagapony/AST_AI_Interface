"""Integration tests for clang-call-analyzer."""

import json
import os
import unittest

from src.compilation_db import CompilationDatabase
from src.ast_parser import ASTParser
from src.function_extractor import FunctionExtractor
from src.function_registry import FunctionRegistry
from src.call_analyzer import CallAnalyzer
from src.relationship_builder import RelationshipBuilder
from src.json_emitter import JSONEmitter


class TestIntegration(unittest.TestCase):
    """Integration test cases for full pipeline."""

    def setUp(self):
        """Set up test fixtures."""
        test_dir = os.path.join(os.path.dirname(__file__), '..', 'test_data')
        self.db_path = os.path.join(test_dir, 'compile_commands.json')

    def test_full_pipeline(self):
        """Test the complete analysis pipeline."""
        # Load compilation database
        db = CompilationDatabase(self.db_path)
        db.load()

        self.assertGreater(len(db.get_units()), 0)

        # Initialize registry
        registry = FunctionRegistry()

        # Parse each translation unit
        for unit in db.get_units():
            parser = ASTParser(unit.flags)
            tu = parser.parse_file(unit.file)

            if not tu:
                continue

            extractor = FunctionExtractor(tu)
            functions = extractor.extract()

            for func in functions:
                registry.add_function(func)

        # Verify functions were found
        self.assertGreater(registry.count(), 0)

        # Build relationships
        call_analyzer = CallAnalyzer(registry)
        relationship_builder = RelationshipBuilder(registry, call_analyzer)
        relationships = relationship_builder.build()

        # Verify relationships
        self.assertEqual(len(relationships), registry.count())

        # Verify that some functions have parents/children
        has_children = any(len(children) > 0 for _, (_, children) in relationships.items())
        self.assertTrue(has_children, "Expected some functions to have children")

        # Test JSON emission
        emitter = JSONEmitter(None)  # Emit to string
        functions_list = registry.get_all()

        # Build output manually for verification
        from dataclasses import asdict
        output_data = []
        for func_idx, func in enumerate(functions_list):
            parents, children = relationships[func_idx]
            output_data.append({
                'index': func_idx,
                'self': {
                    'path': func.path,
                    'lineRange': list(func.line_range),
                    'name': func.name,
                    'qualifiedName': func.qualified_name,
                    'brief': func.brief
                },
                'parents': parents,
                'children': children
            })

        # Verify JSON is valid
        json_str = json.dumps(output_data)
        parsed = json.loads(json_str)
        self.assertEqual(len(parsed), len(functions_list))

    def test_function_relationships(self):
        """Test specific call relationships."""
        # Load and parse
        db = CompilationDatabase(self.db_path)
        db.load()

        registry = FunctionRegistry()

        for unit in db.get_units():
            parser = ASTParser(unit.flags)
            tu = parser.parse_file(unit.file)
            if not tu:
                continue
            extractor = FunctionExtractor(tu)
            for func in extractor.extract():
                registry.add_function(func)

        # Build relationships
        call_analyzer = CallAnalyzer(registry)
        relationship_builder = RelationshipBuilder(registry, call_analyzer)
        relationships = relationship_builder.build()

        # Find specific functions
        compute_idx = None
        add_idx = None
        process_idx = None
        helper_idx = None

        for idx, func in enumerate(registry.get_all()):
            if func.name == 'compute':
                compute_idx = idx
            elif func.name == 'add':
                add_idx = idx
            elif func.name == 'process':
                process_idx = idx
            elif func.name == 'helper':
                helper_idx = idx

        # Verify compute calls process, add, and helper
        self.assertIsNotNone(compute_idx)
        compute_parents, compute_children = relationships[compute_idx]
        self.assertIn(process_idx, compute_children)
        self.assertIn(add_idx, compute_children)
        self.assertIn(helper_idx, compute_children)

        # Verify process is called by compute
        self.assertIsNotNone(process_idx)
        process_parents, _ = relationships[process_idx]
        self.assertIn(compute_idx, process_parents)

    def test_brief_extraction(self):
        """Test that brief descriptions are extracted."""
        db = CompilationDatabase(self.db_path)
        db.load()

        registry = FunctionRegistry()

        for unit in db.get_units():
            parser = ASTParser(unit.flags)
            tu = parser.parse_file(unit.file)
            if not tu:
                continue
            extractor = FunctionExtractor(tu)
            for func in extractor.extract():
                registry.add_function(func)

        # Check that some functions have briefs
        functions_with_brief = [f for f in registry.get_all() if f.brief]
        self.assertGreater(len(functions_with_brief), 0)

        # Find specific functions and check their briefs
        for func in registry.get_all():
            if func.name == 'helper':
                self.assertIsNotNone(func.brief)
                break

    def test_qualified_name_generation(self):
        """Test that qualified names are correctly generated."""
        db = CompilationDatabase(self.db_path)
        db.load()

        registry = FunctionRegistry()

        for unit in db.get_units():
            parser = ASTParser(unit.flags)
            tu = parser.parse_file(unit.file)
            if not tu:
                continue
            extractor = FunctionExtractor(tu)
            for func in extractor.extract():
                registry.add_function(func)

        # Check that qualified names include parameters
        for func in registry.get_all():
            if func.name == 'add':
                self.assertIn('(int, int)', func.qualified_name)
                break


if __name__ == '__main__':
    unittest.main()
