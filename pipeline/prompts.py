INTENT_SCHEMA_DESCRIPTION = """
Return JSON with keys:
- app_name: string
- app_type: string
- features: string[]
- user_roles: string[]
- domain_entities: string[]
- constraints: string[]
- unknowns: string[]
""".strip()


SYSTEM_DESIGN_SCHEMA_DESCRIPTION = """
Return JSON with keys:
- entities: [{name, attributes:[{name,type,required}]}]
- roles: string[]
- flows: [{name, actors:string[], steps:string[]}]
- relationships: string[]
""".strip()


DB_SCHEMA_DESCRIPTION = """
Return JSON with keys:
- tables: [{name, primary_key, fields:[{name,type,required,unique}], foreign_keys:[{field,references_table,references_field}]}]
- relations: [{from_table,from_field,to_table,to_field,relation_type}]
""".strip()


API_SCHEMA_DESCRIPTION = """
Return JSON with key endpoints:
- endpoints: [{name,path,method,request,response,source_table}]
request and response must be flat object maps of field->type.
""".strip()


UI_SCHEMA_DESCRIPTION = """
Return JSON with key pages:
- pages: [{name,route,components:[{id,type,binds_to_endpoint,fields}]}]
""".strip()


AUTH_SCHEMA_DESCRIPTION = """
Return JSON with key roles:
- roles: [{role,permissions:string[]}]
""".strip()


LOGIC_SCHEMA_DESCRIPTION = """
Return JSON with key rules:
- rules: [{id,description,applies_to:string[]}]
""".strip()
