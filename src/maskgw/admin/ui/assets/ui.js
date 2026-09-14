/** @param {unknown} value @returns {value is Record<string, unknown>} */
function record(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    && (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
}
/** @param {unknown} value @returns {value is unknown[]} */
function sequence(value) { return Array.isArray(value); }
/** @param {unknown} value @returns {value is string[]} */
function strings(value) { return sequence(value) && value.every(v => typeof v === "string"); }
const denied = new Set(["__proto__", "constructor", "prototype"]);
/** @param {unknown} value @param {number} depth @param {Set<object>} seen @returns {boolean} */
function safe(value, depth, seen) {
  if (depth > 16) return false;
  if (typeof value === "number") return Number.isSafeInteger(value);
  if (value === null || typeof value === "string" || typeof value === "boolean") return true;
  if (!record(value) && !sequence(value)) return false;
  if (seen.has(value)) return false;
  seen.add(value);
  const ok = Object.keys(value).every(k => !denied.has(k))
    && Object.values(value).every(v => safe(v, depth + 1, seen));
  seen.delete(value);
  return ok;
}
/** @param {unknown} value @param {unknown} node @param {Record<string,unknown>} defs @param {number} depth @returns {boolean} */
function accepts(value, node, defs, depth) {
  if (!record(node) || depth > 32) return false;
  if (typeof node.$ref === "string") return accepts(value, defs[node.$ref.split("/").at(-1) ?? ""], defs, depth+1);
  if ("const" in node && value !== node.const) return false;
  if (sequence(node.enum) && !node.enum.some(v => v === value)) return false;
  if (sequence(node.anyOf) && !node.anyOf.some(n => accepts(value,n,defs,depth+1))) return false;
  if (sequence(node.oneOf) && node.oneOf.filter(n => accepts(value,n,defs,depth+1)).length !== 1) return false;
  if (node.type === "null" && value !== null) return false;
  if (node.type === "boolean" && typeof value !== "boolean") return false;
  if (node.type === "integer" && (typeof value !== "number" || !Number.isSafeInteger(value))) return false;
  if (node.type === "string" && typeof value !== "string") return false;
  if (typeof value === "number") {
    if (typeof node.minimum === "number" && value < node.minimum) return false;
    if (typeof node.maximum === "number" && value > node.maximum) return false;
  }
  if (typeof value === "string") {
    if (typeof node.minLength === "number" && [...value].length < node.minLength) return false;
    if (typeof node.maxLength === "number" && [...value].length > node.maxLength) return false;
  }
  if (node.type === "array") {
    if (!sequence(value)) return false;
    if (typeof node.minItems === "number" && value.length < node.minItems) return false;
    if (typeof node.maxItems === "number" && value.length > node.maxItems) return false;
    if (!value.every(v => accepts(v,node.items,defs,depth+1))) return false;
  }
  if (node.type === "object") {
    if (!record(value) || !record(node.properties)) return false;
    const props = node.properties;
    if (strings(node.required) && !node.required.every(k => Object.hasOwn(value,k))) return false;
    if (!Object.keys(value).every(k => Object.hasOwn(props,k))) return false;
    if (!Object.entries(value).every(([k,v]) => accepts(v,props[k],defs,depth+1))) return false;
  }
  return true;
}
/** @param {unknown} value @returns {value is Record<string,unknown>[]} */
function records(value) { return sequence(value) && value.every(record); }
/** @param {unknown} value @param {unknown} descriptor @returns {boolean} */
function inspect(value, descriptor) {
  if (!record(descriptor) || !record(descriptor.$defs) || !safe(value,0,new Set())) return false;
  if (!accepts(value,descriptor,descriptor.$defs,0) || !record(value)) return false;
  if (!records(value.models) || !records(value.calls) || !records(value.views)
    || !records(value.editors) || !records(value.bindings) || !records(value.messages)) return false;
  const all = [...value.models,...value.calls,...value.views,...value.editors,...value.bindings,...value.messages];
  /** @type {Record<string,unknown>[]} */ const controls=[];
  for (const owner of [...value.views,...value.editors]) {
    if (!records(owner.controls)) return false;
    controls.push(...owner.controls);
  }
  if (controls.length > 512) return false;
  all.push(...controls);
  const ids=all.map(v=>v.id);
  if (!ids.every(v => typeof v === "string" && /^[a-z][0-9]+$/.test(v)) || new Set(ids).size !== ids.length) return false;
  /** @type {Map<string,Record<string,unknown>>} */ const models=new Map();
  for (const item of value.models) {
    if (typeof item.id !== "string" || !record(item.shape)) return false;
    models.set(item.id,item.shape);
  }
  /** @type {Map<string,number>} */ const heights=new Map();
  /** @param {string} key @param {Set<string>} seen @returns {number} */
  function visit(key,seen) {
    const node=models.get(key);
    if (!node || seen.has(key) || seen.size >= 16) return 0;
    const cached=heights.get(key);
    if(cached !== undefined) return cached;
    const next=new Set([...seen,key]);
    /** @type {unknown[]} */ let refs=[];
    if (node.type === "object") {
      if (!records(node.fields)) return 0;
      const names=node.fields.map(f=>f.name);
      if (!names.every(n=>typeof n === "string" && n.length > 0 && !denied.has(n)) || new Set(names).size !== names.length) return 0;
      refs=node.fields.map(f=>f.ref);
    }
    if (node.type === "list" || node.type === "nullable") refs=[node.item];
    if (node.type === "union") {
      if (typeof node.tag !== "string" || !node.tag || denied.has(node.tag) || !records(node.variants)) return 0;
      const values=node.variants.map(v=>JSON.stringify(v.value));
      if (new Set(values).size !== values.length) return 0;
      refs=node.variants.map(v=>v.ref);
      for (const variant of node.variants) {
        if (typeof variant.ref !== "string") return 0;
        const target=models.get(variant.ref);
        if (!target || target.type !== "object" || !records(target.fields)) return 0;
        const link=target.fields.find(f=>f.name === node.tag && f.required === true);
        if (!link || typeof link.ref !== "string") return 0;
        const tag=models.get(link.ref);
        if (!tag || tag.type !== "enum" || !sequence(tag.choices) || tag.choices.length !== 1 || tag.choices[0] !== variant.value) return 0;
      }
    }
    if (typeof node.min === "number" && typeof node.max === "number" && node.min > node.max) return 0;
    if (sequence(node.choices)) {
      const values=node.choices.map(v=>JSON.stringify(v));
      if (new Set(values).size !== values.length) return 0;
    }
    const levels=refs.map(ref=>typeof ref === "string" ? visit(ref,next) : 0);
    if(levels.some(v=>v===0)) return 0;
    const height=1+Math.max(0,...levels);
    if(height>16) return 0;
    heights.set(key,height);
    return height;
  }
  if (![...models.keys()].every(key=>visit(key,new Set()))) return false;
  /** @param {unknown} key @param {unknown} parts @returns {Record<string,unknown> | undefined} */
  function leaf(key,parts) {
    if (typeof key !== "string" || !sequence(parts) || parts.length > 16 || !models.has(key)) return undefined;
    let node=models.get(key);
    for (const part of parts) {
      while (node?.type === "nullable" && typeof node.item === "string") node=models.get(node.item);
      if (typeof part === "string" && part && !denied.has(part) && node?.type === "object" && records(node.fields)) {
        const field=node.fields.find(f=>f.name === part);
        if (!field || typeof field.ref !== "string") return undefined;
        node=models.get(field.ref);
      } else if (typeof part === "number" && Number.isSafeInteger(part) && part >= 0 && node?.type === "list" && typeof node.item === "string") node=models.get(node.item);
      else return undefined;
    }
    return node;
  }
  /** @param {unknown} key @param {unknown} parts */
  function linked(key,parts) { return leaf(key,parts) !== undefined; }
  /** @param {unknown} value @param {Record<string,unknown> | undefined} node @returns {boolean} */
  function fits(value,node) {
    if(value === null || value === undefined) return true;
    while(node?.type === "nullable" && typeof node.item === "string") node=models.get(node.item);
    if(!node) return false;
    if(node.type === "boolean") return typeof value === "boolean";
    if(node.type === "integer") return typeof value === "number" && Number.isSafeInteger(value) && value >= (typeof node.min === "number" ? node.min : 0) && value <= (typeof node.max === "number" ? node.max : Number.MAX_SAFE_INTEGER);
    if(node.type === "enum") return sequence(node.choices) && node.choices.some(v=>v === value);
    if(node.type === "string") {
      if(typeof value !== "string") return false;
      const prefix=typeof node.prefix === "string" ? node.prefix : "";
      const alphabet=typeof node.alphabet === "string" ? node.alphabet : "";
      return [...value].length >= (typeof node.min === "number" ? node.min : 0) && [...value].length <= (typeof node.max === "number" ? node.max : Number.MAX_SAFE_INTEGER) && value.startsWith(prefix) && (!alphabet || [...value.slice(prefix.length)].every(c=>alphabet.includes(c)));
    }
    return false;
  }
  for(const node of models.values()) if(node.type === "object" && records(node.fields)) {
    for(const field of node.fields) if(typeof field.ref !== "string" || !fits(field.default,models.get(field.ref))) return false;
  }
  for(const control of controls) if(!fits(control.default,leaf(control.model,control.path))) return false;
  const calls=new Map(value.calls.map(c=>[c.id,c]));
  for (const call of value.calls) {
    if (typeof call.path !== "string" || !call.path.startsWith("/admin/v1/") || /[?#%\\]|\/\//.test(call.path)) return false;
    const parts=call.path.split("/").slice(3);
    if (parts.some(p=>!p || p === "." || p === "..")) return false;
    const slots=parts.filter(p=>p.includes("{") || p.includes("}"));
    if (slots.length > 1 || (slots.length === 0 && call.identity !== null)) return false;
    if (slots.length === 1 && (typeof call.identity !== "string" || denied.has(call.identity) || !/^[a-z_]+$/.test(call.identity) || slots[0] !== "{"+call.identity+"}")) return false;
    if (typeof call.error !== "string" || !models.has(call.error) || typeof call.output !== "string" || !models.has(call.output)) return false;
    if ((call.method === "GET") !== (call.input === null)) return false;
    if (call.input !== null && (typeof call.input !== "string" || !models.has(call.input))) return false;
  }
  for (const view of value.views) {
    if (calls.get(view.call)?.method !== "GET" || !sequence(view.actions) || !view.actions.every(a=>calls.has(a))) return false;
  }
  for (const editor of value.editors) if (typeof editor.model !== "string" || !models.has(editor.model)) return false;
  for (const control of controls) {
    if (control.projections !== undefined) {
      if(!records(control.projections)) return false;
      for (const projection of control.projections) {
        if(!sequence(projection.paths) || !projection.paths.every(p=>linked(control.model,p))) return false;
        if(!sequence(projection.target) || projection.target.length>16 || !projection.target.every(p=>(typeof p === "string" && p.length>0 && !denied.has(p)) || (typeof p === "number" && Number.isSafeInteger(p) && p>=0))) return false;
      }
    }
  }
  for (const item of [...controls,...value.bindings]) {
    if (!linked(item.model,item.path)) return false;
    if (item.condition !== null && item.condition !== undefined && (!record(item.condition) || !linked(item.model,item.condition.path))) return false;
  }
  return true;
}
export {};

/** @type {unknown} */
const layout={
  "$defs": {
    "Binding": {
      "additionalProperties": false,
      "properties": {
        "id": {
          "title": "Id",
          "type": "string"
        },
        "model": {
          "title": "Model",
          "type": "string"
        },
        "path": {
          "items": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "integer"
              }
            ]
          },
          "title": "Path",
          "type": "array"
        },
        "role": {
          "enum": [
            "version",
            "identity",
            "order",
            "consent",
            "result"
          ],
          "title": "Role",
          "type": "string"
        }
      },
      "required": [
        "id",
        "role",
        "model",
        "path"
      ],
      "title": "Binding",
      "type": "object"
    },
    "Boolean": {
      "additionalProperties": false,
      "properties": {
        "type": {
          "const": "boolean",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "type"
      ],
      "title": "Boolean",
      "type": "object"
    },
    "Call": {
      "additionalProperties": false,
      "properties": {
        "error": {
          "title": "Error",
          "type": "string"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "identity": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Identity"
        },
        "input": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Input"
        },
        "method": {
          "enum": [
            "GET",
            "POST",
            "PUT",
            "DELETE"
          ],
          "title": "Method",
          "type": "string"
        },
        "operation": {
          "enum": [
            "read",
            "create",
            "replace",
            "delete",
            "move",
            "check",
            "confirm",
            "append"
          ],
          "title": "Operation",
          "type": "string"
        },
        "output": {
          "title": "Output",
          "type": "string"
        },
        "path": {
          "title": "Path",
          "type": "string"
        }
      },
      "required": [
        "id",
        "method",
        "path",
        "input",
        "output",
        "error",
        "operation",
        "identity"
      ],
      "title": "Call",
      "type": "object"
    },
    "Choice": {
      "additionalProperties": false,
      "properties": {
        "choices": {
          "items": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "integer"
              },
              {
                "type": "boolean"
              }
            ]
          },
          "minItems": 1,
          "title": "Choices",
          "type": "array"
        },
        "type": {
          "const": "enum",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "type",
        "choices"
      ],
      "title": "Choice",
      "type": "object"
    },
    "Condition": {
      "additionalProperties": false,
      "properties": {
        "path": {
          "items": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "integer"
              }
            ]
          },
          "title": "Path",
          "type": "array"
        },
        "type": {
          "enum": [
            "present",
            "equal",
            "choice",
            "boolean"
          ],
          "title": "Type",
          "type": "string"
        },
        "value": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "boolean"
            },
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Value"
        }
      },
      "required": [
        "type",
        "path"
      ],
      "title": "Condition",
      "type": "object"
    },
    "Control": {
      "additionalProperties": false,
      "properties": {
        "condition": {
          "anyOf": [
            {
              "$ref": "#/$defs/Condition"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "default": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "boolean"
            },
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Default"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "label": {
          "title": "Label",
          "type": "string"
        },
        "model": {
          "title": "Model",
          "type": "string"
        },
        "path": {
          "items": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "integer"
              }
            ]
          },
          "title": "Path",
          "type": "array"
        },
        "projections": {
          "items": {
            "$ref": "#/$defs/Projection"
          },
          "maxItems": 512,
          "title": "Projections",
          "type": "array"
        },
        "type": {
          "enum": [
            "text",
            "integer",
            "checkbox",
            "select",
            "table",
            "list",
            "read",
            "confirm"
          ],
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "id",
        "type",
        "path",
        "model",
        "label"
      ],
      "title": "Control",
      "type": "object"
    },
    "Definition": {
      "additionalProperties": false,
      "properties": {
        "id": {
          "title": "Id",
          "type": "string"
        },
        "shape": {
          "discriminator": {
            "mapping": {
              "boolean": "#/$defs/Boolean",
              "enum": "#/$defs/Choice",
              "integer": "#/$defs/Integer",
              "list": "#/$defs/Sequence",
              "nullable": "#/$defs/Sequence",
              "object": "#/$defs/Object",
              "string": "#/$defs/Text",
              "union": "#/$defs/Union"
            },
            "propertyName": "type"
          },
          "oneOf": [
            {
              "$ref": "#/$defs/Text"
            },
            {
              "$ref": "#/$defs/Integer"
            },
            {
              "$ref": "#/$defs/Boolean"
            },
            {
              "$ref": "#/$defs/Choice"
            },
            {
              "$ref": "#/$defs/Object"
            },
            {
              "$ref": "#/$defs/Sequence"
            },
            {
              "$ref": "#/$defs/Union"
            }
          ],
          "title": "Shape"
        }
      },
      "required": [
        "id",
        "shape"
      ],
      "title": "Definition",
      "type": "object"
    },
    "Editor": {
      "additionalProperties": false,
      "properties": {
        "controls": {
          "items": {
            "$ref": "#/$defs/Control"
          },
          "title": "Controls",
          "type": "array"
        },
        "help": {
          "title": "Help",
          "type": "string"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "model": {
          "title": "Model",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "model",
        "controls",
        "help"
      ],
      "title": "Editor",
      "type": "object"
    },
    "FieldLink": {
      "additionalProperties": false,
      "properties": {
        "default": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "boolean"
            },
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Default"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "ref": {
          "title": "Ref",
          "type": "string"
        },
        "required": {
          "title": "Required",
          "type": "boolean"
        }
      },
      "required": [
        "name",
        "ref",
        "required"
      ],
      "title": "FieldLink",
      "type": "object"
    },
    "Integer": {
      "additionalProperties": false,
      "properties": {
        "max": {
          "default": 9007199254740991,
          "maximum": 9007199254740991,
          "minimum": 0,
          "title": "Max",
          "type": "integer"
        },
        "min": {
          "default": 0,
          "maximum": 9007199254740991,
          "minimum": 0,
          "title": "Min",
          "type": "integer"
        },
        "type": {
          "const": "integer",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "type"
      ],
      "title": "Integer",
      "type": "object"
    },
    "Message": {
      "additionalProperties": false,
      "properties": {
        "id": {
          "title": "Id",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "state": {
          "enum": [
            "loading",
            "authentication",
            "draft",
            "pending",
            "success",
            "conflict",
            "busy",
            "incompatible",
            "unknown",
            "uncertain"
          ],
          "title": "State",
          "type": "string"
        },
        "text": {
          "title": "Text",
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "text",
        "state"
      ],
      "title": "Message",
      "type": "object"
    },
    "Object": {
      "additionalProperties": false,
      "properties": {
        "fields": {
          "items": {
            "$ref": "#/$defs/FieldLink"
          },
          "title": "Fields",
          "type": "array"
        },
        "type": {
          "const": "object",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "type",
        "fields"
      ],
      "title": "Object",
      "type": "object"
    },
    "Projection": {
      "additionalProperties": false,
      "properties": {
        "paths": {
          "items": {
            "items": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "integer"
                }
              ]
            },
            "type": "array"
          },
          "maxItems": 512,
          "title": "Paths",
          "type": "array"
        },
        "source": {
          "enum": [
            "base",
            "draft"
          ],
          "title": "Source",
          "type": "string"
        },
        "target": {
          "items": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "integer"
              }
            ]
          },
          "title": "Target",
          "type": "array"
        },
        "type": {
          "enum": [
            "copy",
            "object",
            "list",
            "omit",
            "insert",
            "replace",
            "remove",
            "permute"
          ],
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "type",
        "source",
        "paths",
        "target"
      ],
      "title": "Projection",
      "type": "object"
    },
    "Sequence": {
      "additionalProperties": false,
      "properties": {
        "item": {
          "title": "Item",
          "type": "string"
        },
        "type": {
          "enum": [
            "list",
            "nullable"
          ],
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "type",
        "item"
      ],
      "title": "Sequence",
      "type": "object"
    },
    "Text": {
      "additionalProperties": false,
      "properties": {
        "alphabet": {
          "default": "",
          "title": "Alphabet",
          "type": "string"
        },
        "max": {
          "default": 9007199254740991,
          "maximum": 9007199254740991,
          "minimum": 0,
          "title": "Max",
          "type": "integer"
        },
        "min": {
          "default": 0,
          "maximum": 9007199254740991,
          "minimum": 0,
          "title": "Min",
          "type": "integer"
        },
        "prefix": {
          "default": "",
          "title": "Prefix",
          "type": "string"
        },
        "type": {
          "const": "string",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "type"
      ],
      "title": "Text",
      "type": "object"
    },
    "Union": {
      "additionalProperties": false,
      "properties": {
        "tag": {
          "title": "Tag",
          "type": "string"
        },
        "type": {
          "const": "union",
          "title": "Type",
          "type": "string"
        },
        "variants": {
          "items": {
            "$ref": "#/$defs/Variant"
          },
          "minItems": 1,
          "title": "Variants",
          "type": "array"
        }
      },
      "required": [
        "type",
        "tag",
        "variants"
      ],
      "title": "Union",
      "type": "object"
    },
    "Variant": {
      "additionalProperties": false,
      "properties": {
        "ref": {
          "title": "Ref",
          "type": "string"
        },
        "value": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "boolean"
            },
            {
              "type": "integer"
            }
          ],
          "title": "Value"
        }
      },
      "required": [
        "value",
        "ref"
      ],
      "title": "Variant",
      "type": "object"
    },
    "View": {
      "additionalProperties": false,
      "properties": {
        "actions": {
          "items": {
            "type": "string"
          },
          "title": "Actions",
          "type": "array"
        },
        "call": {
          "title": "Call",
          "type": "string"
        },
        "controls": {
          "items": {
            "$ref": "#/$defs/Control"
          },
          "title": "Controls",
          "type": "array"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "label": {
          "title": "Label",
          "type": "string"
        }
      },
      "required": [
        "id",
        "label",
        "call",
        "controls",
        "actions"
      ],
      "title": "View",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "bindings": {
      "items": {
        "$ref": "#/$defs/Binding"
      },
      "title": "Bindings",
      "type": "array"
    },
    "calls": {
      "items": {
        "$ref": "#/$defs/Call"
      },
      "maxItems": 19,
      "minItems": 19,
      "title": "Calls",
      "type": "array"
    },
    "editors": {
      "items": {
        "$ref": "#/$defs/Editor"
      },
      "maxItems": 8,
      "minItems": 8,
      "title": "Editors",
      "type": "array"
    },
    "format": {
      "const": 1,
      "title": "Format",
      "type": "integer"
    },
    "messages": {
      "items": {
        "$ref": "#/$defs/Message"
      },
      "title": "Messages",
      "type": "array"
    },
    "models": {
      "items": {
        "$ref": "#/$defs/Definition"
      },
      "maxItems": 128,
      "minItems": 1,
      "title": "Models",
      "type": "array"
    },
    "views": {
      "items": {
        "$ref": "#/$defs/View"
      },
      "maxItems": 6,
      "minItems": 6,
      "title": "Views",
      "type": "array"
    }
  },
  "required": [
    "format",
    "models",
    "calls",
    "views",
    "editors",
    "bindings",
    "messages"
  ],
  "title": "Presentation",
  "type": "object"
};
export const digest="58667c237b89912f66bd035457778be0bcb11ba730d44cefcca22fe5405f2825";
/** @param {unknown} value */
export function check(value) { return inspect(value,layout); }
/** @param {unknown} item @returns {item is Record<string, unknown>} */
export function entry(item) {
  return typeof item === "object" && item !== null && !Array.isArray(item)
    && (Object.getPrototypeOf(item) === Object.prototype || Object.getPrototypeOf(item) === null);
}
/** @param {unknown} item @returns {item is Record<string, unknown>[]} */
function entries(item) { return Array.isArray(item) && item.every(entry); }
/** @param {unknown} item @param {unknown} parts @returns {unknown} */
export function at(item, parts) {
  if (!Array.isArray(parts)) return undefined;
  for (const part of parts) {
    if ((typeof part !== "string" && typeof part !== "number") || ["__proto__","constructor","prototype"].includes(String(part))) return undefined;
    if (Array.isArray(item) && typeof part === "number") item = item[part];
    else if (entry(item) && typeof part === "string" && Object.hasOwn(item,part)) item = item[part];
    else return undefined;
  }
  return item;
}
/** A bounded interpreter of the authenticated descriptor, never wire names.
 * @param {unknown} book
 */
export function reader(book) {
  if (!entry(book) || !entries(book.models) || !entries(book.bindings) || !entries(book.views) || !entries(book.calls)) throw new Error("Request failed.");
  const models = new Map(book.models.map(n=>[n.id,n.shape]));
  const links = book.bindings;
  /** @param {unknown} key @param {unknown} value @param {number} depth @param {Set<object>} seen @param {number[]} versions @param {boolean[]} consents @returns {boolean} */
  function acceptsData(key,value,depth,seen,versions,consents) {
    const node = models.get(key);
    if (!entry(node) || depth > 16) return false;
    if (value !== null && typeof value === "object") {
      if (seen.has(value) || Object.keys(value).some(k=>["__proto__","constructor","prototype"].includes(k))) return false;
    }
    for (const link of links.filter(l=>l.model === key)) {
      const found=at(value,link.path);
      if(found === undefined) continue;
      if(link.role === "version") {
        if(typeof found !== "number" || !Number.isSafeInteger(found) || found < 0) return false;
        versions.push(found);
      }
      if(link.role === "consent") {
        if(typeof found !== "boolean") return false;
        consents.push(found);
      }
    }
    if (node.type === "nullable") return value === null || acceptsData(node.item,value,depth+1,seen,versions,consents);
    if (node.type === "boolean") return typeof value === "boolean";
    if (node.type === "integer") return typeof value === "number" && Number.isSafeInteger(value) && typeof node.min === "number" && typeof node.max === "number" && value >= node.min && value <= node.max;
    if (node.type === "enum") return Array.isArray(node.choices) && node.choices.some(v=>v === value);
    if (node.type === "string") {
      if(typeof value !== "string" || typeof node.min !== "number" || typeof node.max !== "number") return false;
      const prefix=typeof node.prefix === "string" ? node.prefix : "";
      const alphabet=typeof node.alphabet === "string" ? node.alphabet : "";
      return [...value].length >= node.min && [...value].length <= node.max && value.startsWith(prefix) && (!alphabet || [...value.slice(prefix.length)].every(c=>alphabet.includes(c)));
    }
    if (node.type === "union" && typeof node.tag === "string" && entries(node.variants) && entry(value)) {
      const tag=node.tag;
      const target=node.variants.find(n=>n.value === value[tag]);
      return !!target && acceptsData(target.ref,value,depth+1,seen,versions,consents);
    }
    if (node.type === "list") {
      if(!Array.isArray(value)) return false;
      const next=new Set([...seen,value]);
      const ids=new Set();
      for(let index=0;index<value.length;index++) {
        const child=value[index];
        if(!acceptsData(node.item,child,depth+1,next,versions,consents)) return false;
        for(const link of links.filter(l=>l.model === node.item)) {
          const found=at(child,link.path);
          if(found === undefined) continue;
          if(link.role === "order" && found !== index) return false;
          if(link.role === "identity" && found !== null) { if(ids.has(found)) return false; ids.add(found); }
        }
      }
      return true;
    }
    if (node.type === "object" && entries(node.fields) && entry(value)) {
      const fields=node.fields;
      if(Object.keys(value).some(k=>!fields.some(f=>f.name === k))) return false;
      const next=new Set([...seen,value]);
      return fields.every(f=>typeof f.name === "string" && (Object.hasOwn(value,f.name) ? acceptsData(f.ref,value[f.name],depth+1,next,versions,consents) : f.required === false));
    }
    return false;
  }
  /** @param {unknown} key @param {unknown} value */
  function inspectData(key,value) {
    /** @type {number[]} */ const versions=[];
    /** @type {boolean[]} */ const consents=[];
    if(!acceptsData(key,value,0,new Set(),versions,consents) || new Set(versions).size > 1 || new Set(consents).size > 1) throw new Error("Request failed.");
    const version=versions[0];
    if(version !== undefined && consents.some(c=>c !== (version > 0))) throw new Error("Request failed.");
    return version;
  }
  const calls=book.calls;
  const views=book.views.map(view=>{
    const call=calls.find(c=>c.id === view.call);
    if(typeof view.id !== "string" || typeof view.label !== "string" || !entries(view.controls)
      || !call || typeof call.id !== "string" || call.method !== "GET" || call.identity !== null) throw new Error("Request failed.");
    return {id:view.id,label:view.label,call:call.id,controls:view.controls};
  });
  /** @param {string} id @param {unknown} value */
  function inspectDataFor(id,value) {
    const call=calls.find(c=>c.id === id && c.method === "GET");
    if(!call) throw new Error("Request failed.");
    const version=inspectData(call.output,value);
    if(version === undefined) throw new Error("Request failed.");
    return version;
  }
  /** @param {unknown} key @param {unknown} value @param {string} role */
  function bound(key,value,role) {
    return links.filter(l=>l.model === key && l.role === role).map(l=>at(value,l.path)).filter(v=>v !== undefined);
  }
  return {views,inspectData,inspectDataFor,bound};
}


/** @typedef {"authentication" | "conflict" | "busy" | "incompatible" | "unknown" | "uncertain"} FailureKind */
/** @typedef {{kind:"success",version:number,message:string} | {kind:FailureKind,version:number | undefined,message:string}} Outcome */
/** @typedef {{id:string,version:number,draft:unknown,identity:string | undefined}} Command */
/** @param {unknown} value @returns {number} */
export function safeVersion(value) {
  if(typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) throw new Error("Request refused.");
  return value;
}
/** Copy JSON data without accessors, custom prototypes, coercion or shared references.
 * @param {unknown} value @param {number} depth @param {Set<object>} seen @returns {unknown}
 */
export function capture(value,depth=0,seen=new Set()) {
  if(depth > 16) throw new Error("Request refused.");
  if(value === null || typeof value === "string" || typeof value === "boolean") return value;
  if(typeof value === "number" && Number.isSafeInteger(value)) return value;
  if(typeof value !== "object" || value === null || seen.has(value) || (!Array.isArray(value) && !entry(value))) throw new Error("Request refused.");
  const next=new Set([...seen,value]);
  const descriptors=Object.getOwnPropertyDescriptors(value);
  if(Reflect.ownKeys(value).some(k=>typeof k !== "string" || ["__proto__","constructor","prototype"].includes(k))) throw new Error("Request refused.");
  for(const [key,d] of Object.entries(descriptors)) if(!("value" in d) || (!d.enumerable && !(Array.isArray(value) && key === "length"))) throw new Error("Request refused.");
  if(Array.isArray(value)) {
    if(Object.keys(value).length !== value.length) throw new Error("Request refused.");
    return Object.freeze(value.map(v=>capture(v,depth+1,next)));
  }
  return Object.freeze(Object.fromEntries(Object.entries(value).map(([k,v])=>[k,capture(v,depth+1,next)])));
}
/** @param {unknown} value @returns {value is Record<string,unknown>[]} */
function commandEntries(value) { return Array.isArray(value) && value.every(entry); }
/** The model itself is the closed object/list/select-copy projection plan.
 * No caller supplies field paths, destinations, methods or executable projections.
 * @param {unknown} source
 */
export function commands(source) {
  const book=capture(source);
  if(!entry(book) || !commandEntries(book.calls) || !commandEntries(book.models) || !commandEntries(book.bindings) || !commandEntries(book.messages)) throw new Error("Request refused.");
  const catalog=book.calls, models=new Map(book.models.map(m=>[m.id,m.shape])), links=book.bindings, messages=book.messages;
  const lens=reader(book);
  /** @param {string} id */
  function lookup(id) {
    const call=catalog.find(c=>c.id === id);
    if(!call || typeof call.path !== "string" || typeof call.output !== "string" || typeof call.error !== "string"
      || (call.method !== "GET" && call.method !== "POST" && call.method !== "PUT" && call.method !== "DELETE")
      || (call.identity !== null && typeof call.identity !== "string")) throw new Error("Request refused.");
    return {id,path:call.path,output:call.output,error:call.error,input:call.input,operation:call.operation,identity:call.identity,method:call.method};
  }
  /** Locate the identity leaf in the paired authenticated read model.
   * @param {unknown} key @param {number} depth @returns {unknown[]}
   */
  function leaves(key,depth=0) {
    const shape=models.get(key);if(!entry(shape) || depth > 16) throw new Error("Request refused.");
    if(shape.type === "nullable") return leaves(shape.item,depth+1);
    if(shape.type !== "object" || !commandEntries(shape.fields)) return [];
    const fields=shape.fields;
    return fields.flatMap(f=>links.some(l=>l.model === key && l.role === "identity" && Array.isArray(l.path) && l.path.length === 1 && l.path[0] === f.name) ? [f.ref] : leaves(f.ref,depth+1));
  }
  /** @param {ReturnType<typeof lookup>} call @param {string | undefined} identity */
  function resolve(call,identity) {
    if(call.identity === null) {if(identity !== undefined) throw new Error("Request refused.");return call.path;}
    if(typeof identity !== "string" || !identity || /[%/?#\\{}:]|\s/.test(identity) || [".","..","__proto__","constructor","prototype"].includes(identity)) throw new Error("Request refused.");
    const parts=call.path.split("/"), marker="{"+call.identity+"}";
    if(parts.filter(p=>p === marker).length !== 1 || parts.some(p=>/[{}]/.test(p) && p !== marker)) throw new Error("Request refused.");
    const paired=catalog.find(c=>c.path === call.path && c.method === "GET");
    if(!paired) throw new Error("Request refused.");
    const keys=leaves(paired.output);if(keys.length !== 1) throw new Error("Request refused.");
    const shape=models.get(keys[0]);
    const key=entry(shape) && shape.type === "nullable" ? shape.item : keys[0];
    lens.inspectData(key,identity);
    return parts.map(p=>p === marker ? identity : p).join("/");
  }
  /** Construct only the declared writable fields; the bound version has a separate source.
   * @param {Command} command
   */
  function prepare(command) {
    const call=lookup(command.id), version=safeVersion(command.version);
    if(call.method === "GET" || !["create","replace","delete","move","confirm","append"].includes(String(call.operation)) || version === Number.MAX_SAFE_INTEGER) throw new Error("Request refused.");
    if(call.operation === "confirm" ? version !== 0 : version === 0) throw new Error("Request refused.");
    const shape=models.get(call.input), draft=capture(command.draft);
    if(!entry(shape) || shape.type !== "object" || !commandEntries(shape.fields) || !entry(draft)) throw new Error("Request refused.");
    const fields=shape.fields;
    const bindings=links.filter(l=>l.model === call.input && l.role === "version");
    const binding=bindings[0];
    if(bindings.length !== 1 || !binding || !Array.isArray(binding.path) || binding.path.length !== 1 || typeof binding.path[0] !== "string") throw new Error("Request refused.");
    const slot=binding.path[0];
    if(Object.keys(draft).some(k=>k === slot || !fields.some(f=>f.name === k))) throw new Error("Request refused.");
    const body=Object.fromEntries(fields.flatMap(f=>typeof f.name !== "string" ? [] : f.name === slot ? [[f.name,version]] : Object.hasOwn(draft,f.name) ? [[f.name,at(draft,[f.name])]] : []));
    lens.inspectData(call.input,body);
    return {call,path:resolve(call,command.identity),body:capture(body),version};
  }
  /** @param {ReturnType<typeof lookup>} call @param {unknown} value @param {number} status @param {number} base @returns {Outcome} */
  function outcome(call,value,status,base) {
    safeVersion(base);
    const data=capture(value);
    if(status >= 200 && status < 300) {
      const version=lens.inspectData(call.output,data);
      if(version !== base+1 || !Number.isSafeInteger(version) || lens.bound(call.output,data,"result").length !== 1 || lens.bound(call.output,data,"result")[0] !== true) throw new Error("Request refused.");
      return {kind:"success",version,message:"Salva; visualização ainda não atualizada."};
    }
    const version=lens.inspectData(call.error,data), shape=models.get(call.error);
    if(!entry(shape) || shape.type !== "union" || typeof shape.tag !== "string") throw new Error("Request refused.");
    const name=at(data,[shape.tag]), message=messages.find(m=>m.name === name);
    if(!message || typeof message.text !== "string") throw new Error("Request refused.");
    const kind=message.state;
    if(kind !== "authentication" && kind !== "conflict" && kind !== "busy" && kind !== "incompatible" && kind !== "unknown" && kind !== "uncertain") throw new Error("Request refused.");
    if(status < 400 || status > 599 || (kind === "busy" && status !== 409) || (kind === "conflict" && status !== 409 && status !== 404)
      || (kind === "uncertain" && (status !== 500 || version !== base+1)) || (kind === "authentication" && status !== 401)) throw new Error("Request refused.");
    return {kind,version,message:message.text};
  }
  return Object.freeze({lookup,resolve,prepare,outcome});
}


/** @param {unknown} value @returns {Record<string,unknown>[]} */
function rows(value) {if(!Array.isArray(value) || !value.every(entry)) throw new Error("Request refused.");return value;}
/** @param {unknown} value @returns {string} */
function word(value) {if(typeof value !== "string") throw new Error("Request refused.");return value;}
/** @param {unknown} value @returns {Record<string,unknown>} */
function authorRecord(value) {if(!entry(value)) throw new Error("Request refused.");return value;}
/** @param {unknown} value @returns {string[]} */
function trail(value) {if(!Array.isArray(value) || !value.every(v=>typeof v === "string" && !["__proto__","constructor","prototype"].includes(v))) throw new Error("Request refused.");return value;}
/** @param {unknown} source */
export function author(source) {
  const book=capture(source);if(!entry(book)) throw new Error("Request refused.");
  const calls=rows(book.calls), views=rows(book.views), models=rows(book.models), links=rows(book.bindings), editors=rows(book.editors), messages=rows(book.messages), lens=reader(book);
  /** @param {unknown} key */
  function shape(key) {const value=models.find(m=>m.id === key)?.shape;if(!entry(value)) throw new Error("Request refused.");return value;}
  /** @param {unknown} key */
  function fields(key) {return rows(shape(key).fields);}
  /** @param {unknown} key @param {string} role */
  function slot(key,role) {return links.filter(l=>l.model === key && l.role === role).map(l=>trail(l.path)[0]).filter(v=>v !== undefined);}
  const checkCall=authorRecord(calls.find(c=>c.operation === "check")), consentCall=authorRecord(calls.find(c=>c.operation === "confirm"));
  if(!checkCall || !consentCall) throw new Error("Request refused.");
  const home=views.find(v=>Array.isArray(v.actions) && v.actions.includes(checkCall.id));if(!home) throw new Error("Request refused.");
  const homeCall=authorRecord(calls.find(c=>c.id === home.call));
  const documentField=authorRecord(fields(homeCall.output).find(f=>shape(f.ref).type === "object"));
  const consent=rows(home.controls).find(c=>c.type === "confirm" && c.model === consentCall.input);if(!consent) throw new Error("Request refused.");
  /** @param {unknown} value */
  function documentValue(value) {const clean=capture(value);lens.inspectData(homeCall.output,clean);const doc=at(clean,[word(documentField.name)]);if(!entry(doc)) throw new Error("Request refused.");return doc;}
  /** @param {unknown} key @param {unknown} value @param {boolean} transient @returns {unknown} */
  function omit(key,value,transient) {
    const node=shape(key);
    if(node.type === "nullable") return value === null ? null : omit(node.item,value,transient);
    if(node.type === "list") {if(!Array.isArray(value)) throw new Error("Request refused.");return value.map(v=>omit(node.item,v,transient));}
    if(node.type !== "object") return value;
    if(!entry(value)) throw new Error("Request refused.");
    const excluded=[...slot(key,"order"),...(transient ? [...slot(key,"identity"),...slot(key,"version")] : [])];
    return Object.fromEntries(fields(key).filter(f=>!excluded.includes(word(f.name)) && Object.hasOwn(value,word(f.name))).map(f=>[word(f.name),omit(f.ref,value[word(f.name)],transient)]));
  }
  const profiles=views.flatMap(view=>{
    const actions=calls.filter(c=>Array.isArray(view.actions) && view.actions.includes(c.id));
    const create=actions.find(c=>c.operation === "create");if(!create) return [];
    const replace=actions.find(c=>c.operation === "replace"), remove=actions.find(c=>c.operation === "delete");if(!replace || !remove) throw new Error("Request refused.");
    const container=fields(create.input).find(f=>shape(f.ref).type === "object");if(!container) throw new Error("Request refused.");
    const controls=rows(view.controls).filter(c=>c.model === container.ref && c.type !== "confirm");
    const target=trail(rows(controls[0]?.projections)[0]?.target);if(target.length !== 1) throw new Error("Request refused.");
    const listField=fields(documentField.ref).find(f=>f.name === target[0]);if(!listField || shape(listField.ref).type !== "list") throw new Error("Request refused.");
    const itemKey=shape(listField.ref).item, identity=slot(itemKey,"identity")[0];if(!identity) throw new Error("Request refused.");
    const nested=fields(container.ref).find(f=>shape(f.ref).type === "object");
    const choice=controls.find(c=>c.type === "select" && shape(fields(container.ref).find(f=>f.name === trail(c.path)[0])?.ref).type === "string");
    const warning=rows(view.controls).find(c=>c.type === "confirm");
    const listing=calls.find(c=>c.id === view.call);if(!listing) throw new Error("Request refused.");
    const list=fields(listing.output).find(f=>shape(f.ref).type === "list");if(!list) throw new Error("Request refused.");
    return [{id:word(view.id),label:word(view.label),create:word(create.id),replace:word(replace.id),remove:word(remove.id),member:word(container.name),model:word(container.ref),controls,target,itemKey,identity,listing:word(list.name),output:listing.output,nested:nested ? word(nested.name) : undefined,choice:choice ? trail(choice.path)[0] : undefined,warning:warning ? word(warning.label) : undefined}];
  });
  /** @param {string} id */
  function profile(id) {const result=profiles.find(p=>p.id === id);if(!result) throw new Error("Request refused.");return result;}
  /** @param {string} id @param {unknown} value */
  function items(id,value) {const p=profile(id), list=at(documentValue(value),p.target);if(!Array.isArray(list)) throw new Error("Request refused.");return list;}
  /** @param {string} id @param {unknown} value */
  function content(id,value) {
    const p=profile(id), clean=authorRecord(capture(value));
    const result=Object.fromEntries(fields(p.model).filter(f=>Object.hasOwn(clean,word(f.name))).map(f=>[word(f.name),clean[word(f.name)]]));
    lens.inspectData(p.model,result);return capture(result);
  }
  /** @param {string} id @param {unknown} value */
  function defaults(id,value=undefined) {
    const p=profile(id);if(value !== undefined) return content(id,value);
    return capture(Object.fromEntries(p.controls.filter(c=>c.default !== null).map(c=>[word(trail(c.path)[0]),c.default])));
  }
  /** @param {string} id @param {unknown} value @param {unknown} registry */
  function checkedContent(id,value,registry) {
    const p=profile(id), clean=capture(value);lens.inspectData(p.model,clean);
    if(p.choice && p.nested) {
      const name=at(clean,[p.choice]), editor=editors.find(e=>e.name === name);
      if(!editor || !available(registry).includes(word(name))) throw new Error("Request refused.");
      const detail=at(clean,[p.nested]);lens.inspectData(editor.model,detail);
      for(const control of rows(editor.controls)) {
        const present=at(detail,control.path) !== undefined;
        if(entry(control.condition)) {
          const enabled=at(detail,control.condition.path) === control.condition.value;
          if(enabled !== present) throw new Error("Request refused.");
        }
      }
    }
    return clean;
  }
  // The sole unassociated, non-template read with a list of editor names is the registry.
  const registryCall=authorRecord(calls.find(c=>c.method === "GET" && c.identity === null && !views.some(v=>v.call === c.id)));
  /** @param {unknown} registry */
  function available(registry) {
    lens.inspectData(registryCall.output,registry);
    const list=fields(registryCall.output).find(f=>shape(f.ref).type === "list");if(!list) throw new Error("Request refused.");
    const values=at(registry,[word(list.name)]);if(!Array.isArray(values)) throw new Error("Request refused.");
    return editors.filter(e=>values.some(v=>{
      if(!entry(v) || v.name !== e.name) return false;
      const names=Object.values(v).flatMap(x=>Array.isArray(x) ? x : []);
      const wanted=rows(e.controls).map(c=>trail(c.path)[0]);
      return names.length === wanted.length && wanted.every(n=>names.includes(n));
    })).map(e=>word(e.name));
  }
  /** @param {unknown} base @param {{page:string,operation:"create"|"replace"|"delete",value:unknown,identity:string|undefined} | undefined} edit */
  function candidate(base,edit=undefined) {
    const doc=documentValue(base);let draft={...doc};
    if(edit) {
      const p=profile(edit.page), list=items(p.id,base), index=list.findIndex(v=>at(v,[p.identity]) === edit.identity);
      if(edit.operation !== "create" && index < 0) throw new Error("Request refused.");
      const value=capture(edit.value);if(edit.operation !== "delete") lens.inspectData(p.model,value);
      const next=[...list];
      if(edit.operation === "create") next.push(value);
      else if(edit.operation === "delete") next.splice(index,1);
      else {const prior=next[index];if(!entry(prior) || !entry(value)) throw new Error("Request refused.");next[index]={...value,[p.identity]:prior[p.identity]};}
      draft={...draft,[word(p.target[0])]:next};
    }
    // New identities never enter this transient projection. The snapshot stays intact.
    const result=capture(omit(documentField.ref,draft,true));lens.inspectData(checkCall.input,result);return result;
  }
  /** @param {unknown} value */
  function consented(value) {lens.inspectData(homeCall.output,value);return lens.bound(homeCall.output,value,"consent")[0] === true;}
  return Object.freeze({profiles,profile,items,content,defaults,checkedContent,available,candidate,consented,shape,fields,editors,
    /** @param {string} id @param {unknown} value */ listed:(id,value)=>{const p=profile(id);lens.inspectData(p.output,value);return rows(at(value,[p.listing]));},
    /** @param {string} id @param {unknown} value */ changeable:(id,value)=>{const p=profile(id);lens.inspectData(p.output,value);return lens.bound(p.output,value,"consent")[0] === true;},
    home:word(home.id),read:word(home.call),registry:word(registryCall.id),check:word(checkCall.id),
    consent:{call:word(consentCall.id),field:word(trail(consent.path)[0]),text:word(consent.label),label:word(rows(home.controls).find(c=>c.type === "confirm" && Array.isArray(c.path) && c.path.length === 0)?.label)},
    /** @param {unknown} value */ inspectCheck:value=>{lens.inspectData(checkCall.output,value);},
    /** @param {unknown} value */ inspectError:value=>{lens.inspectData(checkCall.error,value);return messages;},
    /** @param {string} id @param {unknown} base @param {unknown} value @param {string|undefined} identity */ known:(id,base,value,identity)=>{
      const p=profile(id), list=items(id,base), index=identity === undefined ? list.length : list.findIndex(v=>at(v,[p.identity]) === identity);
      if(index < 0) throw new Error("Request refused.");
      const common=p.controls.map(c=>({path:[...p.target,index,...trail(c.path)].join("."),label:word(c.label)}));
      const selected=p.choice ? at(value,[p.choice]) : undefined, editor=editors.find(e=>e.name === selected);
      if(editor && p.nested) for(const c of rows(editor.controls)) common.push({path:[...p.target,index,p.nested,...trail(c.path)].join("."),label:word(c.label)});
      return common;
    },
    /** @param {unknown} value @param {{path:string,label:string}[]} known */ reasons:(value,known)=>{
      lens.inspectData(checkCall.error,value);
      if(!entry(value) || !Array.isArray(value.fields)) return [];
      return value.fields.flatMap(item=>{
        if(!entry(item)) return [];
        const control=known.find(k=>k.path === item.path);
        const message=messages.find(m=>Object.entries(item).some(([k,v])=>k !== "path" && v === m.name));
        return control && message ? [{label:control.label,text:word(message.text)}] : [];
      });
    },
  });
}


/** @param {unknown} value @returns {value is Record<string, unknown>} */
function object(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** @param {string} path @param {boolean} first */
function destination(path, first) {
  if (first ? path !== "/admin/ui/presentation.json" : !path.startsWith("/admin/v1/")) throw new Error("Request refused.");
  if (/[?#%\\{}]|\/\//.test(path) || path.split("/").some(v => v === "." || v === "..")) throw new Error("Request refused.");
  const url = new URL(path, window.location.origin);
  if (url.origin !== window.location.origin || url.pathname !== path) throw new Error("Request refused.");
  return url;
}

/** Entry is explicit; no DOM, persistent state, automatic request or write.
 * @param {string} token
 * @param {AbortSignal | undefined} signal
 * @param {() => void} expired
 */
export async function open(token, signal=undefined, expired=()=>{}) {
  if (!token || /[\r\n]/.test(token)) throw new Error("Request refused.");
  const stop = new AbortController();
  let ended = false;
  let writing = false;
  /** @type {Set<() => void>} */ const listeners=new Set();
  /** @type {Map<string, {path:string, method:"GET" | "POST", operation:string, output:string}>} */ const calls = new Map();
  /** @type {ReturnType<typeof reader> | undefined} */ let lens;
  /** @type {ReturnType<typeof commands> | undefined} */ let actions;
  /** @type {ReturnType<typeof author> | undefined} */ let forms;
  function close() { ended=true; token=""; calls.clear(); lens=undefined; actions=undefined; forms=undefined; stop.abort(); signal?.removeEventListener("abort",close); for(const listener of listeners) listener(); listeners.clear(); }
  signal?.addEventListener("abort",close,{once:true});
  if(signal?.aborted) close();
  /** @param {string} path @param {string} method @param {string | undefined} body @param {boolean} first @param {AbortSignal | undefined} extra @param {boolean} errors */
  async function send(path, method, body, first, extra=undefined,errors=false) {
    if(ended) throw new AccessError("authentication");
    if(extra?.aborted) throw new AccessError("unknown");
    const url = destination(path, first);
    if (body !== undefined && (body.includes(JSON.stringify(token).slice(1,-1)) || new TextEncoder().encode(body).length > 1048576)) throw new Error("Request refused.");
    const headers = new Headers();
    headers.set("Authorization", "Bearer " + token);
    if (body !== undefined) headers.set("Content-Type", "application/json");
    const response = await fetch(url, {
      signal:AbortSignal.any([stop.signal,AbortSignal.timeout(30000),...(extra ? [extra] : [])]), method, headers, ...(body === undefined ? {} : {body}), mode: "cors",
      credentials: "omit", redirect: "error", cache: "no-store", referrerPolicy: "no-referrer",
    });
    if(ended) throw new AccessError("authentication");
    if(response.status === 401) { close(); expired(); throw new AccessError("authentication"); }
    if ((!response.ok && !errors) || response.headers.get("Content-Type") !== "application/json") throw new AccessError("unknown");
    return response;
  }
  try {
    const response = await send("/admin/ui/presentation.json", "GET", undefined, true);
    const bytes = await response.arrayBuffer();
    if (bytes.byteLength > 262144) throw new Error("Request refused.");
    const sum = await crypto.subtle.digest("SHA-256", bytes);
    const hex = [...new Uint8Array(sum)].map(v => v.toString(16).padStart(2,"0")).join("");
    if (hex !== digest) throw new Error("Request refused.");
    /** @type {unknown} */ const data = JSON.parse(new TextDecoder("utf-8", {fatal:true}).decode(bytes));
    if (!check(data) || !object(data) || !Array.isArray(data.calls)) throw new Error("Request refused.");
    const frozen=capture(data);
    lens=reader(frozen); actions=commands(frozen);
    /** @type {unknown[]} */ const entries = data.calls;
    for (const item of entries) {
      if (object(item) && typeof item.id === "string" && typeof item.path === "string" && typeof item.output === "string" && item.identity === null
        && ((item.method === "GET" && item.operation === "read") || (item.method === "POST" && item.operation === "check"))) {
        calls.set(item.id, {path:item.path, method:item.method, operation:item.operation, output:item.output});
      }
    }
    /** @param {string} id @param {"GET" | "POST"} method @param {unknown} body @param {AbortSignal | undefined} extra */
    async function run(id, method, body, extra=undefined) {
      try {
        const call = calls.get(id);
        if (!call || call.method !== method) throw new Error("Request refused.");
        if(method === "POST") {
          if(!actions || !lens) throw new AccessError("authentication");
          lens.inspectData(actions.lookup(id).input,capture(body));
        }
        const response = await send(call.path, method, method === "GET" ? undefined : JSON.stringify(body), false, extra);
        /** @type {unknown} */ const value = await response.json();
        if(ended || extra?.aborted || !lens) throw new AccessError("authentication");
        if(JSON.stringify(value).includes(JSON.stringify(token).slice(1,-1))) throw new AccessError("incompatible");
        lens.inspectData(call.output,value);
        return capture(value);
      } catch (error) { if(ended) throw new AccessError("authentication"); if(error instanceof AccessError) throw error; throw new AccessError("unknown"); }
    }
    if(ended) throw new AccessError("authentication");
    return Object.freeze({
      close,
      /** @param {() => void} listener */ onClose: listener=>{ if(ended) listener(); else listeners.add(listener); return ()=>{listeners.delete(listener);}; },
      describe: () => { if(ended || !lens) throw new AccessError("authentication"); return lens; },
      design: () => {if(ended) throw new AccessError("authentication");forms ??= author(frozen);return forms;},
      /** @param {unknown} candidate @param {{path:string,label:string}[]} known @param {AbortSignal | undefined} extra */
      assess: async(candidate,known=[],extra=undefined)=>{
        if(ended || writing || !lens || !actions) throw new AccessError("incompatible");
        forms ??= author(frozen);
        const plan=forms, call=actions.lookup(plan.check), clean=capture(candidate);
        lens.inspectData(call.input,clean);
        const response=await send(call.path,call.method,JSON.stringify(clean),false,extra,true);
        /** @type {unknown} */ const value=await response.json();
        if(ended || extra?.aborted) throw new AccessError("authentication");
        if(JSON.stringify(value).includes(JSON.stringify(token).slice(1,-1))) throw new AccessError("incompatible");
        if(response.ok) {plan.inspectCheck(value);return {ok:true,issues:[]};}
        return {ok:false,issues:plan.reasons(value,known)};
      },
      /** @param {Command} command */ prepare: command=>{
        if(ended || !actions) throw new AccessError("authentication");
        const prepared=actions.prepare(command);
        const body=JSON.stringify(prepared.body);
        if(body.includes(JSON.stringify(token).slice(1,-1)) || new TextEncoder().encode(body).length > 1048576) throw new AccessError("incompatible");
        destination(prepared.path,false);
      },
      /** @param {Command} command @param {AbortSignal | undefined} extra @returns {Promise<Outcome>} */
      mutate: async(command,extra=undefined)=>{
        if(ended || !actions) throw new AccessError("authentication");
        if(writing) throw new AccessError("incompatible");
        const prepared=actions.prepare(command);
        const body=JSON.stringify(prepared.body);
        // Full checking precedes the flight and every bearer construction.
        if(extra?.aborted || body.includes(JSON.stringify(token).slice(1,-1)) || new TextEncoder().encode(body).length > 1048576) throw new AccessError("incompatible");
        destination(prepared.path,false);
        writing=true;
        try {
          const response=await send(prepared.path,prepared.call.method,body,false,extra,true);
          /** @type {unknown} */ const value=await response.json();
          if(ended || !actions) throw new AccessError("authentication");
          if(extra?.aborted || JSON.stringify(value).includes(JSON.stringify(token).slice(1,-1))) throw new AccessError("unknown");
          return actions.outcome(prepared.call,value,response.status,prepared.version);
        } catch(error) {
          if(ended) throw new AccessError("authentication");
          return {kind:"unknown",version:undefined,message:"Resultado desconhecido. Releia o estado antes de decidir."};
        } finally {writing=false;}
      },
      /** @param {string} id @param {AbortSignal | undefined} extra */ read: (id, extra=undefined) => run(id, "GET", undefined,extra),
      /** @param {string} id @param {unknown} body */ check: (id, body) => run(id, "POST", body),
    });
  } catch (error) { close(); if(error instanceof AccessError) throw error; throw new AccessError("unknown"); }
}


export class AccessError extends Error {
  /** @param {"authentication" | "incompatible" | "unknown"} kind */
  constructor(kind) { super("Request failed."); this.kind=kind; }
}


/** @typedef {{value:unknown,version:number}} Snapshot */
/** @typedef {{base:Snapshot,draft:unknown,command:Command}} Editing */
/** @typedef {{tag:"authentication"} | {tag:"loading"} | {tag:"reading",snapshot:Snapshot} | {tag:"draft",edit:Editing} | {tag:"pending",edit:Editing} | {tag:"success",edit:Editing,version:number,newBase:Snapshot | undefined,message:string} | {tag:"conflict" | "busy" | "incompatible" | "unknown" | "uncertain",edit:Editing | undefined,newBase:Snapshot | undefined,message:string}} Flow */
/** @typedef {Awaited<ReturnType<typeof open>>} WriteClient */

/** Pure coordinator: no DOM control, timer, queue or implicit business operation.
 * The caller must explicitly choose a read and confirm each abstract command.
 * @param {WriteClient} client @param {string} readId
 */
export function coordinate(client,readId) {
  /** @type {Flow} */ let state={tag:"loading"};
  let generation=0, sequence=0, closed=false, occupied=false, minimum=0;
  /** @type {AbortController | undefined} */ let active;
  /** @type {Snapshot | undefined} */ let observed;
  /** @type {() => void} */ let detach=()=>{};
  function clear() {
    if(closed) return;
    closed=true;generation++;sequence++;active?.abort();active=undefined;observed=undefined;state={tag:"authentication"};occupied=false;minimum=0;detach();
    if(typeof window !== "undefined" && typeof window.removeEventListener === "function") {window.removeEventListener("pagehide",close);window.removeEventListener("pageshow",close);}
  }
  function close() {clear();client.close();}
  detach=client.onClose(clear);
  if(!closed && typeof window !== "undefined" && typeof window.addEventListener === "function") {window.addEventListener("pagehide",close);window.addEventListener("pageshow",close);}
  /** @param {unknown} value */
  function snapshot(value) { const clean=capture(value);return Object.freeze({value:clean,version:safeVersion(client.describe().inspectDataFor(readId,clean))}); }
  /** @param {unknown} error */
  function expires(error) {if(error instanceof AccessError && error.kind === "authentication") {close();return true;}return false;}
  async function load() {
    if(closed || occupied || (state.tag !== "loading" && state.tag !== "reading" && !(state.tag === "incompatible" && !state.edit))) return false;
    const mine=generation,ticket=++sequence;active?.abort();active=new AbortController();state={tag:"loading"};
    try {const value=await client.read(readId,active.signal);if(closed || mine !== generation || ticket !== sequence) return false;state={tag:"reading",snapshot:snapshot(value)};return true;}
    catch(error) {if(!closed && mine === generation && ticket === sequence && !expires(error)) state={tag:"incompatible",edit:undefined,newBase:undefined,message:"Leitura indisponível. Tente novamente."};return false;}
  }
  /** Begin/replace an abstract draft only after an explicit, checked read.
   * @param {string} id @param {unknown} draft @param {string | undefined} identity
   */
  function begin(id,draft,identity=undefined) {
    if(closed || occupied || state.tag !== "reading") return false;
    const clean=capture(draft), base=state.snapshot;
    const command=Object.freeze({id,version:safeVersion(base.version),draft:clean,identity});
    client.prepare(command);
    sequence++;active?.abort();observed=undefined;minimum=base.version;
    state={tag:"draft",edit:Object.freeze({base,draft:clean,command})};return true;
  }
  /** Polls can only record a separate observation while a draft exists.
   * @param {unknown} value
   */
  function poll(value) {
    if(closed || occupied || state.tag === "pending" || (state.tag !== "reading" && state.tag !== "draft")) return false;
    const fresh=snapshot(value);
    if(state.tag === "reading") {
      if(fresh.version < state.snapshot.version) return false;
      if(fresh.version === state.snapshot.version && JSON.stringify(fresh.value) !== JSON.stringify(state.snapshot.value)) throw new Error("Request refused.");
      state={tag:"reading",snapshot:fresh};
    } else {
      if(fresh.version < state.edit.base.version || (observed && fresh.version < observed.version)) return false;
      if(fresh.version === state.edit.base.version && JSON.stringify(fresh.value) !== JSON.stringify(state.edit.base.value)) throw new Error("Request refused.");
      observed=fresh;
    }
    return true;
  }
  /** Readback never attributes a higher version to a lost command. */
  async function reconcile() {
    if(closed || occupied || !["success","conflict","unknown","uncertain"].includes(state.tag)) return false;
    const prior=state;
    if(prior.tag !== "success" && prior.tag !== "conflict" && prior.tag !== "unknown" && prior.tag !== "uncertain") return false;
    state={...prior,newBase:undefined,message:prior.tag === "success" ? "Salva; visualização ainda não atualizada." : prior.message};
    occupied=true;const mine=generation,ticket=++sequence;active=new AbortController();
    try {
      const value=await client.read(readId,active.signal);
      if(closed || mine !== generation || ticket !== sequence) return false;
      const fresh=snapshot(value), floor=prior.tag === "success" ? prior.version : prior.edit?.base.version;
      if(fresh.version < minimum || (floor !== undefined && fresh.version < floor)) throw new Error("Request refused.");
      state={...prior,newBase:fresh,message:prior.tag === "success" ? "Salva; visualização atualizada." : prior.message};return true;
    } catch(error) {if(!closed && mine === generation && ticket === sequence) expires(error);return false;}
    finally {if(mine === generation && ticket === sequence) {occupied=false;active=undefined;}}
  }
  /** Confirmed content and its base travel as one frozen command. */
  async function confirm() {
    if(closed || occupied || (state.tag !== "draft" && state.tag !== "busy")) return false;
    const edit=state.edit;if(!edit) return false;
    client.prepare(edit.command);
    occupied=true;sequence++;active?.abort();active=new AbortController();const mine=generation,ticket=sequence;
    state={tag:"pending",edit};
    try {
      const result=await client.mutate(edit.command,active.signal);
      if(closed || mine !== generation || ticket !== sequence) return false;
      if(result.version !== undefined) safeVersion(result.version);
      minimum=result.version ?? edit.base.version;
      if(result.kind === "authentication") {close();return false;}
      if(result.kind === "success") {
        if(result.version !== edit.base.version+1) throw new Error("Request refused.");
        state={tag:"success",edit,version:result.version,newBase:undefined,message:result.message};
      } else state={tag:result.kind,edit,newBase:undefined,message:result.message};
    } catch(error) {
      if(closed || mine !== generation || ticket !== sequence || expires(error)) return false;
      state={tag:"unknown",edit,newBase:undefined,message:"Resultado desconhecido. Releia o estado antes de decidir."};
    } finally {if(mine === generation && ticket === sequence) {occupied=false;active=undefined;}}
    if(!closed) await reconcile();
    return !closed;
  }
  // Abort only ends waiting locally; it does not assert server cancellation.
  function cancel() {
    if(closed || !occupied) return false;
    if(state.tag === "pending") {
      const edit=state.edit;sequence++;active?.abort();active=undefined;occupied=false;
      state={tag:"unknown",edit,newBase:undefined,message:"Resultado desconhecido. Releia o estado antes de decidir."};return true;
    }
    return false;
  }
  /** Explicit human review is required to choose a conflict's separate base.
   * @param {unknown} draft
   */
  function review(draft) {
    if(closed || occupied || state.tag !== "conflict" || !state.newBase || !state.edit) return false;
    const edit=state.edit, base=state.newBase, clean=capture(draft);
    const command=Object.freeze({...edit.command,version:safeVersion(base.version),draft:clean});
    client.prepare(command);state={tag:"draft",edit:Object.freeze({base,draft:clean,command})};observed=undefined;return true;
  }
  function finish() {
    if(closed || occupied || state.tag !== "success" || !state.newBase) return false;
    state={tag:"reading",snapshot:state.newBase};observed=undefined;return true;
  }
  /** @param {unknown} draft */
  function change(draft) {
    if(closed || occupied || state.tag !== "draft") return false;
    const edit=state.edit, clean=capture(draft), command=Object.freeze({...edit.command,draft:clean});
    client.prepare(command);state={tag:"draft",edit:Object.freeze({...edit,draft:clean,command})};return true;
  }
  function discard() {
    if(closed || occupied || state.tag !== "draft") return false;
    state={tag:"reading",snapshot:state.edit.base};observed=undefined;return true;
  }
  return Object.freeze({load,begin,poll,confirm,cancel,reconcile,review,finish,change,discard,close,release:clear,
    getState:()=>Object.freeze(state),getObservation:()=>observed});
}


/** @typedef {Awaited<ReturnType<typeof open>>} WorkClient */
/** @typedef {ReturnType<WorkClient["design"]>} Design */
/** @typedef {{page:string,operation:"create"|"replace"|"delete",identity:string|undefined}} Intent */
/** Local editing owns one coordinator and one modal. No operation starts implicitly.
 * @param {WorkClient} client @param {HTMLElement} root @param {() => void} refreshed
 */
export function workbench(client,root,refreshed) {
  const plan=client.design();
  /** @type {ReturnType<typeof coordinate> | undefined} */ let flow;
  /** @type {HTMLDialogElement | undefined} */ let dialog;
  /** @type {HTMLElement | undefined} */ let restore;
  /** @type {Intent | undefined} */ let intent;
  /** @type {unknown} */ let base;
  /** @type {unknown} */ let raw;
  /** @type {unknown} */ let registry;
  /** @type {AbortController | undefined} */ let active;
  let ended=false, engaged=false, dirty=false, waiting=false, serial=0, checked=false, locked=false, examining=false;
  /** @type {HTMLParagraphElement | undefined} */ let note;
  /** @type {HTMLElement | undefined} */ let proof;
  /** @type {() => void} */ let detach=()=>{};
  function dismiss() {if(dialog) {dialog.close();erase(dialog);dialog.remove();dialog=undefined;}if(restore?.isConnected) restore.focus();}
  function reset() {serial++;active?.abort();active=undefined;flow?.release();flow=undefined;intent=undefined;base=undefined;raw=undefined;registry=undefined;dirty=false;engaged=false;waiting=false;examining=false;checked=false;proof=undefined;note=undefined;dismiss();}
  function close() {ended=true;reset();detach();restore=undefined;}
  detach=client.onClose(close);
  /** @param {string} text @param {() => void} action */
  function button(text,action) {const b=element("button",text);b.type="button";b.addEventListener("click",action);return b;}
  /** @param {string} text */
  function announce(text) {if(note) note.textContent=text;}
  /** @param {HTMLDialogElement} box */
  function trap(box) {
    box.addEventListener("keydown",event=>{
      if(event.key !== "Tab") return;
      const focusable=Array.from(box.querySelectorAll("button,input,select,textarea,[tabindex]"))
        .filter(n=>n instanceof HTMLElement && n.tabIndex >= 0 && !n.hasAttribute("disabled") && n.getClientRects().length > 0);
      const index=focusable.indexOf(document.activeElement ?? box), target=event.shiftKey ? focusable.at(-1) : focusable[0];
      if(index < 0 || (event.shiftKey ? index === 0 : index === focusable.length-1)) {event.preventDefault();if(target instanceof HTMLElement) target.focus();else box.focus();}
    });
  }
  /** @param {string} title @param {() => void} cancel */
  function modal(title,cancel) {
    dismiss();dialog=element("dialog");const heading=element("h2",title);heading.id="edit-title";heading.tabIndex=-1;
    dialog.setAttribute("aria-labelledby",heading.id);note=element("p");note.setAttribute("role","status");note.setAttribute("aria-live","polite");
    dialog.append(heading,note);dialog.addEventListener("cancel",event=>{event.preventDefault();cancel();});
    trap(dialog);root.append(dialog);dialog.showModal();heading.focus();return dialog;
  }
  /** @param {() => void} action */
  function leave(action) {
    if(waiting) {announce("Operação pendente. Aguarde o desfecho.");return;}
    if(!engaged || !dirty) {reset();action();return;}
    const prior=dialog;if(!prior) return;
    // Keep the original controls in memory, inert under the nested modal.
    const confirm=element("dialog"), title=element("h2","Descartar rascunho?");title.id="discard-title";
    confirm.setAttribute("aria-labelledby",title.id);confirm.append(title,element("p","As alterações não salvas serão descartadas."));
    const keep=()=>{confirm.close();erase(confirm);confirm.remove();prior.focus();};
    confirm.append(button("Continuar editando",keep),button("Descartar",()=>{keep();reset();action();}));
    confirm.addEventListener("cancel",event=>{event.preventDefault();keep();});trap(confirm);root.append(confirm);confirm.showModal();
  }
  /** @param {string} title */
  async function start(title) {
    if(ended || engaged) return false;
    engaged=true;restore=document.activeElement instanceof HTMLElement ? document.activeElement : undefined;
    active=new AbortController();flow=coordinate(client,plan.read);const ticket=++serial;waiting=true;
    const box=modal(title,()=>leave(()=>{}));box.append(button("Cancelar",()=>leave(()=>{})));announce("Carregando…");
    const good=await flow.load();
    if(ended || ticket !== serial) return false;
    waiting=false;const state=flow.getState();
    if(!good || state.tag !== "reading") {announce("Leitura indisponível. Feche e tente novamente.");return false;}
    base=state.snapshot.value;return true;
  }
  /** @param {string} page @param {"create"|"replace"|"delete"} operation @param {string | undefined} identity */
  async function edit(page,operation,identity=undefined) {
    try {
      if(locked) return;
      if(!await start(operation === "create" ? "Criar item" : operation === "replace" ? "Editar item" : "Excluir item")) return;
      const p=plan.profile(page);if(!plan.consented(base)) {announce("Adoção explícita necessária antes de editar.");return;}
      const selected=operation === "create" ? undefined : plan.items(page,base).find(v=>at(v,[p.identity]) === identity);
      if(operation !== "create" && selected === undefined) {announce("Item indisponível. Atualize a leitura.");return;}
      intent={page,operation,identity};
      if(operation === "delete") {raw={};renderDelete();return;}
      const ticket=serial;waiting=true;registry=await client.read(plan.registry,active?.signal);
      if(ended || ticket !== serial) return;waiting=false;
      if(client.describe().inspectDataFor(plan.registry,registry) !== client.describe().inspectDataFor(plan.read,base)) throw new Error("Request refused.");
      raw=plan.defaults(page,selected);
      if(selected !== undefined) plan.checkedContent(page,raw,registry);
      renderForm();
    } catch {if(!ended) {waiting=false;announce("Conteúdo incompatível. A leitura foi preservada; edição bloqueada.");}}
  }
  function changedDraft() {checked=false;if(proof) erase(proof);dialog?.querySelectorAll("[aria-describedby]").forEach(n=>n.removeAttribute("aria-describedby"));serial++;active?.abort();active=new AbortController();if(examining) {waiting=false;examining=false;}dirty=true;announce("Rascunho não salvo. Resultado anterior descartado.");}
  /** @param {Record<string,unknown>} control @param {Record<string,unknown>} values @param {HTMLElement} parent @param {() => void} changed */
  function controlNode(control,values,parent,changed) {
    if(!Array.isArray(control.path) || typeof control.path[0] !== "string" || typeof control.label !== "string") throw new Error("Request refused.");
    const key=control.path[0], field=plan.fields(control.model).find(f=>f.name === key);if(!field) throw new Error("Request refused.");
    const shape=plan.shape(field.ref), label=element("label",control.label), id="field-"+String(control.id);
    const node=control.type === "select" ? element("select") : element("input");node.id=id;label.htmlFor=id;
    if(node instanceof HTMLSelectElement) {
      const empty=element("option","Escolha explicitamente");empty.value="";node.append(empty);
      const choices=Array.isArray(shape.choices) ? shape.choices : plan.available(registry);
      for(const choice of choices) {const option=element("option",String(choice));option.value=String(choice);node.append(option);}
      node.value=typeof values[key] === "string" ? values[key] : "";
    } else {
      node.autocomplete="off";node.spellcheck=false;
      node.type=control.type === "checkbox" ? "checkbox" : "text";
      if(control.type === "integer") node.inputMode="numeric";
      if(node.type === "checkbox") node.checked=values[key] === true;
      else node.value=values[key] === undefined ? "" : String(values[key]);
    }
    const update=()=>{
      if((waiting && !examining) || ended) return;
      let value;
      if(node instanceof HTMLInputElement && node.type === "checkbox") value=node.checked;
      else if(control.type === "integer") value=/^(0|[1-9][0-9]*)$/.test(node.value) && Number.isSafeInteger(Number(node.value)) ? Number(node.value) : node.value;
      else value=node.value;
      values[key]=value;changedDraft();changed();
    };
    node.addEventListener(node instanceof HTMLSelectElement || control.type === "checkbox" ? "change" : "input",update);parent.append(label,node);return node;
  }
  function renderForm() {
    if(!intent || !entry(raw)) return;
    const p=plan.profile(intent.page);let values={...raw};
    const box=modal(intent.operation === "create" ? "Criar item" : "Editar item",()=>leave(()=>{})), form=element("form");form.noValidate=true;
    const detail=element("section");
    function sync() {raw=capture(values);}
    function nested() {
      const focusId=document.activeElement instanceof HTMLElement && (detail.compareDocumentPosition(document.activeElement) & Node.DOCUMENT_POSITION_CONTAINED_BY) ? document.activeElement.id : undefined;
      erase(detail);if(!p.choice || !p.nested) return;
      const editor=plan.editors.find(e=>e.name === values[p.choice ?? ""]);if(!editor) return;
      const parentKey=p.nested, prior=values[parentKey];const local=entry(prior) ? {...prior} : {};
      for(const c of rowsForControls(editor.controls)) if(Array.isArray(c.path) && typeof c.path[0] === "string" && !Object.hasOwn(local,c.path[0]) && c.default !== null) local[c.path[0]]=c.default;
      values[parentKey]=local;detail.append(element("p",typeof editor.help === "string" ? editor.help : ""));
      for(const c of rowsForControls(editor.controls)) {
        if(entry(c.condition) && at(local,c.condition.path) !== c.condition.value) {if(Array.isArray(c.path) && typeof c.path[0] === "string") delete local[c.path[0]];continue;}
        controlNode(c,local,detail,()=>{sync();if(c.type === "checkbox") nested();});
      }
      sync();
      if(focusId) {const target=document.getElementById(focusId);if(target && (detail.compareDocumentPosition(target) & Node.DOCUMENT_POSITION_CONTAINED_BY)) target.focus();}
    }
    for(const c of p.controls) controlNode(c,values,form,()=>{
      if(Array.isArray(c.path) && c.path[0] === p.choice && p.nested) {values[p.nested]={};nested();}
      sync();
    });
    nested();sync();form.append(detail);
    const examine=button("Validar proposta",()=>{void examineDraft();});
    const save=element("button","Salvar");save.type="submit";
    form.append(examine,save,button("Cancelar",()=>leave(()=>{})));box.append(form);
    form.addEventListener("submit",event=>{event.preventDefault();if(waiting) return;try {if(!intent) return;plan.checkedContent(intent.page,raw,registry);if(p.warning) confirmNotice(p.warning,()=>{void commit();});else void commit();} catch {announce("Confira os campos conhecidos antes de salvar.");}});
  }
  /** @param {string} text @param {() => void} action */
  function confirmNotice(text,action) {
    const box=modal("Confirmar operação",()=>renderForm());box.append(element("p",text),button("Cancelar",()=>renderForm()),button("Confirmar",action));
  }
  function renderDelete() {
    const box=modal("Excluir item",()=>leave(()=>{}));box.append(element("p","Confirme a exclusão somente deste item."),button("Cancelar",()=>leave(()=>{})),button("Excluir",()=>{void commit();}));
  }
  async function examineDraft() {
    if(ended || waiting || !base) return;
    let ticket=serial;
    try {
      const edit=intent ? {...intent,value:plan.checkedContent(intent.page,raw,registry)} : undefined;
      const candidate=plan.candidate(base,edit);ticket=++serial;waiting=true;examining=true;active=new AbortController();announce("Validando conteúdo…");
      const known=intent ? plan.known(intent.page,base,raw,intent.identity) : [];
      const result=await client.assess(candidate,known,active.signal);
      if(ended || ticket !== serial) return;
      checked=result.ok;announce(result.ok ? "Conteúdo e compilação válidos. Não salvo; conexão não testada; não garante segurança para todos os dados." : "Proposta inválida. Confira os campos conhecidos.");
      if(proof) {erase(proof);proof.remove();}proof=element("section");dialog?.append(proof);
      if(!result.ok) for(const [index,issue] of result.issues.entries()) {
        const message=element("p",issue.label+": "+issue.text);message.id="reason-"+index;proof.append(message);
        const label=Array.from(dialog?.querySelectorAll("label") ?? []).find(n=>n.textContent === issue.label);
        label?.control?.setAttribute("aria-describedby",message.id);
      }
    } catch {if(!ended && ticket === serial) announce("Validação indisponível ou incompatível. Nenhuma gravação foi solicitada.");}
    finally {if(ticket === serial) {waiting=false;examining=false;}}
  }
  async function commit() {
    if(ended || waiting || !flow) return;
    try {
      if(intent) {
        const p=plan.profile(intent.page), body=intent.operation === "delete" ? {} : {[p.member]:plan.checkedContent(intent.page,raw,registry)};
        const call=intent.operation === "create" ? p.create : intent.operation === "replace" ? p.replace : p.remove;
        if(flow.getState().tag === "reading") flow.begin(call,body,intent.identity);
        else if(flow.getState().tag === "draft") flow.change(body);
      }
      const ticket=serial;waiting=true;checked=false;dirty=true;
      const pending=flow.confirm();renderOutcome();await pending;
      if(ended || ticket !== serial) return;waiting=false;renderOutcome();
    } catch {if(!ended) {waiting=false;announce("Operação recusada. Rascunho preservado.");}}
  }
  function renderOutcome() {
    if(!flow || ended) return;
    const state=flow.getState(), box=modal("Resultado da operação",()=>{});
    if(state.tag === "unknown" || state.tag === "uncertain" || state.tag === "incompatible") locked=true;
    announce("message" in state ? state.message : state.tag === "pending" ? "Operação pendente. Não repita." : "Confira o estado.");
    if("edit" in state && state.edit) {box.append(element("h3","Base original"),plain(state.edit.base.value),element("h3","Rascunho preservado"),plain(raw));}
    if("newBase" in state && state.newBase) box.append(element("h3","Nova base separada"),plain(state.newBase.value));
    if(waiting) return;
    if(state.tag === "success" && state.newBase) box.append(button("Concluir",()=>{if(flow?.finish()) {reset();refreshed();}}));
    if(["success","conflict","unknown","uncertain"].includes(state.tag)) box.append(button("Reler estado",()=>{void (async()=>{if(!flow || waiting) return;waiting=true;const ticket=serial;await flow.reconcile();if(!ended && ticket === serial) {waiting=false;renderOutcome();}})();}));
    if(state.tag === "busy") box.append(button("Tentar novamente",()=>{void commit();}));
    if(state.tag === "conflict" && state.newBase && intent && intent.operation !== "delete") box.append(button("Revisar rascunho com nova base",()=>{
      if(!flow || !intent) return;const p=plan.profile(intent.page);
      try {if(flow.review({[p.member]:plan.checkedContent(p.id,raw,registry)})) {base=state.newBase?.value;checked=false;renderForm();}} catch {announce("Revisão incompatível. Rascunho preservado.");}
    }));
    box.append(button("Fechar e descartar rascunho",()=>leave(()=>refreshed())));
  }
  async function consentStart() {
    if(locked) return;
    if(!await start("Adoção explícita")) return;
    if(plan.consented(base)) {announce("Já adotada. Atualize a leitura; não repita a operação.");return;}
    const box=modal("Adoção explícita",()=>leave(()=>{})), label=element("label","Li e compreendi as consequências"), input=element("input");input.type="checkbox";input.checked=false;input.id="consent-entry";label.htmlFor=input.id;
    const submit=button(plan.consent.label,()=>{
      if(waiting || !input.checked || !flow) return;
      flow.begin(plan.consent.call,{[plan.consent.field]:true});void commit();
    });submit.disabled=true;input.addEventListener("change",()=>{submit.disabled=!input.checked;});
    box.append(element("p",plan.consent.text),label,input,button("Cancelar",()=>leave(()=>{})),submit);
  }
  /** @param {HTMLElement} panel @param {string} page @param {unknown} value */
  function attach(panel,page,value) {
    if(ended || engaged) return;
    if(page === plan.home) {
      panel.append(button("Validar documento",()=>{void (async()=>{if(await start("Validar documento")) await examineDraft();})();}));
      if(!plan.consented(value)) panel.append(button("Adoção explícita",()=>{void consentStart();}));
    }
    const p=plan.profiles.find(v=>v.id === page);if(!p) return;
    const permitted=!locked && plan.changeable(page,value), add=button("Criar",()=>{void edit(page,"create");});add.disabled=!permitted;panel.append(add);
    if(locked) panel.append(element("p","Escritas bloqueadas nesta sessão. Verificação operacional necessária."));
    if(!plan.changeable(page,value)) panel.append(element("p","Adoção explícita necessária antes de editar."));
    for(const [index,item] of plan.listed(page,value).entries()) {
      const identity=at(item,[p.identity]);if(typeof identity !== "string") continue;
      const row=element("section");row.append(element("h3","Item "+(index+1)));
      const change=button("Editar",()=>{void edit(page,"replace",identity);}), remove=button("Excluir",()=>{void edit(page,"delete",identity);});change.disabled=!permitted;remove.disabled=!permitted;row.append(change,remove);panel.append(row);
    }
  }
  return {attach,leave,close,active:()=>engaged,pending:()=>waiting,examined:()=>checked};
}
/** @param {unknown} value @returns {Record<string,unknown>[]} */
function rowsForControls(value) {if(!Array.isArray(value) || !value.every(entry)) throw new Error("Request refused.");return value;}


/** @template {keyof HTMLElementTagNameMap} K @param {K} tag @param {string} text */
export function element(tag,text="") { const node=document.createElement(tag); node.textContent=text; return node; }
/** @param {unknown} value @returns {HTMLElement} */
export function plain(value) {
  if(Array.isArray(value)) {
    if(!value.length) return element("p","Lista vazia.");
    const list=element("ol");
    for(const item of value) { const row=element("li"); row.append(plain(item)); list.append(row); }
    return list;
  }
  if(entry(value)) {
    if(!Object.keys(value).length) return element("p","Sem valores.");
    const list=element("dl");
    for(const [key,item] of Object.entries(value)) { const body=element("dd"); body.append(plain(item)); list.append(element("dt",key),body); }
    return list;
  }
  return element("span",value === null ? "Não informado" : value === true ? "Sim" : value === false ? "Não" : String(value));
}
/** @param {HTMLElement} node */
export function erase(node) {
  node.querySelectorAll("input,select,textarea").forEach(input=>{if(input instanceof HTMLInputElement || input instanceof HTMLSelectElement || input instanceof HTMLTextAreaElement) input.value="";});
  node.querySelectorAll("input").forEach(input=>{input.checked=false;});
  node.querySelectorAll("*").forEach(child=>child.replaceChildren());
  node.replaceChildren();
}
/** @typedef {Awaited<ReturnType<typeof open>>} Client */
/** @typedef {ReturnType<Client["describe"]>["views"][number]} PageItem */
/** @typedef {{tag:"authentication"} | {tag:"pending",stop:AbortController} | {tag:"ready",client:Client,stop:AbortController,views:PageItem[]}} Access */
/** @typedef {{tag:"loading"} | {tag:"success",value:unknown,version:number,time:number} | {tag:"unknown",prior:Sheet | undefined,stale:boolean}} Sheet */

/** Installs only a local entry form; all private labels arrive after entry.
 * @param {HTMLElement} root
 */
export function mount(root) {
  /** @type {Access} */ let access={tag:"authentication"};
  /** @type {Sheet | undefined} */ let sheet;
  /** @type {AbortController | undefined} */ let flight;
  let generation=0, turn=0, selected=0, busy=false, paused=true;
  /** @type {ReturnType<typeof setTimeout> | undefined} */ let timer;
  /** @type {HTMLElement | undefined} */ let panel;
  /** @type {HTMLElement | undefined} */ let notice;
  /** @type {HTMLButtonElement | undefined} */ let retry;
  /** @type {ReturnType<typeof workbench> | undefined} */ let editor;
  function stopClock() { if(timer !== undefined) clearTimeout(timer); timer=undefined; }
  function clear() {
    generation++; turn++; flight?.abort(); flight=undefined; stopClock(); paused=true; busy=false; sheet=undefined;
    editor?.close();editor=undefined;
    if(access.tag === "ready") access.client.close();
    if(access.tag !== "authentication") access.stop.abort();
    access={tag:"authentication"}; panel=undefined; notice=undefined; retry=undefined;
    // Erase detached descendants as well as removing them from the live tree.
    erase(root);
  }
  /** @param {string} message @param {boolean} focus */
  function login(message="",focus=true) {
    clear();
    const heading=element("h1","Acesso local");
    const form=element("form");
    const label=element("label","Token");
    const input=element("input"); input.id="entry-key"; input.type="password"; input.autocomplete="off"; input.spellcheck=false; input.required=true;
    label.htmlFor=input.id;
    const enter=element("button","Entrar"); enter.type="submit";
    const info=element("p",message); info.setAttribute("role","status"); info.setAttribute("aria-live","polite");
    form.append(label,input,enter);root.append(heading,form,info);
    form.addEventListener("submit",event=>{
      event.preventDefault();
      if(access.tag !== "authentication") return;
      let key=input.value; input.value="";
      if(!key) { info.textContent="Autenticação necessária."; input.focus(); return; }
      const stop=new AbortController();access={tag:"pending",stop};
      const mine=++generation;
      enter.disabled=true; info.textContent="Carregando…";
      const attempt=open(key,stop.signal,()=>{if(mine === generation) login("Autenticação necessária.");}); key="";
      void attempt.then(client=>{
        if(mine !== generation) {client.close();return;}
        access={tag:"ready",client,stop,views:client.describe().views}; selected=0;
        editor=workbench(client,root,()=>{sheet=undefined;shell();void load(true);});
        shell(); void load(true);
      }).catch(()=>{ if(mine === generation) login("Não foi possível entrar. Tente novamente."); });
    });
    if(focus) input.focus();
  }
  function shell() {
    if(access.tag !== "ready") return;
    erase(root);
    const top=element("header");top.append(element("h1","Administração local"));
    const leave=element("button","Sair"); leave.type="button"; leave.addEventListener("click",()=>login());top.append(leave);
    const nav=element("nav"); nav.setAttribute("aria-label","Navegação");
    for(const [index,view] of access.views.entries()) {
      const button=element("button",view.label);button.type="button";
      if(index === selected) button.setAttribute("aria-current","page");
      button.addEventListener("click",()=>{
        if(access.tag !== "ready") return;
        const navigate=()=>{selected=index; sheet=undefined; shell(); void load(true);};
        if(editor?.active()) editor.leave(navigate);else navigate();
      });
      nav.append(button);
    }
    notice=element("p");notice.setAttribute("role","status");notice.setAttribute("aria-live","polite");
    retry=element("button","Atualizar");retry.type="button";retry.addEventListener("click",()=>{if(editor?.active()) editor.leave(()=>{void load(true);});else void load(true);});
    panel=element("section"); panel.setAttribute("aria-label","Leitura");
    root.append(top,nav,notice,retry,panel);
  }
  /** @param {boolean} focus */
  function show(focus) {
    if(access.tag !== "ready" || !panel || !notice) return;
    const view=access.views[selected]; if(!view) return;
    const restore=focus || document.activeElement === panel.firstElementChild;
    erase(panel);
    const title=element("h2",view.label); title.tabIndex=-1; panel.append(title);
    if(sheet?.tag === "success") {
      for(const control of view.controls) {
        if(control.type !== "read" || typeof control.label !== "string") continue;
        const section=element("section");section.append(element("h3",control.label),plain(at(sheet.value,control.path)));panel.append(section);
      }
      notice.textContent="Respondendo · Última leitura: "+new Date(sheet.time).toLocaleTimeString();
      editor?.attach(panel,view.id,sheet.value);
    } else if(sheet?.tag === "unknown") {
      notice.textContent=sheet.stale ? "Leitura desatualizada. Tente novamente." : "Leitura indisponível. Tente novamente.";
      if(sheet.prior?.tag === "success") {
        for(const control of view.controls) if(control.type === "read" && typeof control.label === "string") {
          const section=element("section");section.append(element("h3",control.label),plain(at(sheet.prior.value,control.path)));panel.append(section);
        }
      }
    } else notice.textContent="Carregando…";
    if(retry) retry.disabled=busy;
    if(restore) title.focus();
  }
  function schedule() {
    stopClock();
    if(access.tag === "ready" && !paused && !busy && document.visibilityState === "visible") timer=setTimeout(()=>{void poll();},15000);
  }
  /** @param {boolean} focus */
  async function load(focus) {
    if(access.tag !== "ready") return;
    const client=access.client, view=access.views[selected]; if(!view) return;
    flight?.abort(); flight=new AbortController();
    const mine=generation, ticket=++turn; busy=true;paused=true;stopClock();
    const prior=sheet?.tag === "success" ? sheet : sheet?.tag === "unknown" ? sheet.prior : undefined;
    sheet={tag:"loading"};show(focus);
    try {
      const value=await client.read(view.call,flight.signal);
      if(mine !== generation || ticket !== turn) return;
      // The transport has already checked this envelope before it reaches state.
      const book=client.describe();
      const version=book.inspectDataFor(view.call,value);
      sheet={tag:"success",value,version,time:Date.now()};paused=false;
    } catch(error) {
      if(mine !== generation || ticket !== turn) return;
      if(error instanceof AccessError && error.kind === "authentication") { login("Autenticação necessária.");return; }
      sheet={tag:"unknown",prior,stale:prior !== undefined};paused=true;
    } finally { if(mine === generation && ticket === turn) { busy=false;show(false);schedule(); } }
  }
  async function poll() {
    if(access.tag !== "ready" || busy || paused || editor?.active() || document.visibilityState !== "visible") {schedule();return;}
    const client=access.client, first=access.views[0];if(!first) return;
    flight=new AbortController();
    const mine=generation, ticket=++turn;busy=true;show(false);
    try {
      const value=await client.read(first.call,flight.signal);
      if(mine !== generation || ticket !== turn) return;
      const version=client.describe().inspectDataFor(first.call,value);
      if(sheet?.tag === "success" && version !== sheet.version) {
        sheet={tag:"unknown",prior:undefined,stale:true};paused=true;
      } else if(selected === 0) sheet={tag:"success",value,version,time:Date.now()};
    } catch(error) {
      if(mine !== generation || ticket !== turn) return;
      if(error instanceof AccessError && error.kind === "authentication") { login("Autenticação necessária.");return; }
      sheet={tag:"unknown",prior:sheet?.tag === "success" ? sheet : undefined,stale:sheet?.tag === "success"};paused=true;
    } finally {if(mine === generation && ticket === turn) {busy=false;show(false);schedule();}}
  }
  const hide=()=>login("",false);
  const appear=()=>login("",true);
  const visibility=()=>{if(document.visibilityState !== "visible") stopClock();else schedule();};
  window.addEventListener("pagehide",hide);window.addEventListener("pageshow",appear);document.addEventListener("visibilitychange",visibility);
  login("",false);
  return ()=>{clear();window.removeEventListener("pagehide",hide);window.removeEventListener("pageshow",appear);document.removeEventListener("visibilitychange",visibility);};
}

if(typeof document !== "undefined") {
  const root=document.querySelector("main");
  if(root instanceof HTMLElement) mount(root);
}
