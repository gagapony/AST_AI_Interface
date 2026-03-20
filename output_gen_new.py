        output_paths = _determine_output_paths(args)

        # Generate outputs
        # True serial structure: compile_commands.json → call_graph.json → callgraph.html
        json_path = None

        # Step 1: Always generate JSON if format is html or all
        if args.format == 'html' or args.format == 'all':
            # Generate JSON file first (HTML will be generated from JSON)
            json_path = Path(str(output_paths.get('json', '/tmp/call_graph_temp.json')))
            logging.info(f"Generating JSON output to {json_path}")
            emitter = JSONEmitter(str(json_path))
            emitter.emit(functions_to_emit, relationships_to_emit)
            logging.info(f"JSON generated at {json_path}")

        # Step 2: Generate other formats
        if args.format == 'json' or args.format == 'all':
            # If format is 'all', we already generated JSON, nothing more to do
            if args.format == 'json':
                logging.info(f"Generating JSON output to {output_paths['json']}")
                if not output_paths.get('json'):
                    emitter = JSONEmitter(str(output_paths['json']))
                    emitter.emit(functions_to_emit, relationships_to_emit)
                logging.info(f"JSON output: {output_paths.get('json')}")

        # Step 3: Generate HTML (always from JSON file)
        if args.format == 'html' or args.format == 'all':
            # Generate ECharts HTML (always from JSON file)
            logging.info("Generating ECharts HTML from JSON...")
            if not json_path:
                logging.error("JSON path not available for HTML generation")
                return 1

            # Load JSON to get proper format
            with open(json_path, 'r', encoding='utf-8') as f:
                import json as json_lib
                functions_dict = json_lib.load(f)

            # Remove temp JSON file
            import os
            if 'call_graph_temp.json' in str(json_path):
                os.remove(json_path)
                logging.info(f"Removed temporary JSON file: {json_path}")

            # Generate HTML from JSON
            echarts_gen = EChartsGenerator(
                functions=functions_dict,
                relationships=relationships_to_emit,
                logger=logger
            )
            html_content = echarts_gen.generate_html()
            write_html_file(html_content, str(output_paths['html']))
            logging.info(f"HTML output: {output_paths.get('html')}")
