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
export const digest="0ec27cb80cb0111532e82cb2ef765810037550c33d06980b2aabc679f519a6ea";
/** @param {unknown} value */
export function check(value) { return inspect(value,layout); }

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
 */
export async function open(token) {
  if (!token || /[\r\n]/.test(token)) throw new Error("Request refused.");
  /** @param {string} path @param {"GET" | "POST"} method @param {string | undefined} body @param {boolean} first */
  async function send(path, method, body, first) {
    const url = destination(path, first);
    if (body !== undefined && body.includes(token)) throw new Error("Request refused.");
    const headers = new Headers();
    headers.set("Authorization", "Bearer " + token);
    if (body !== undefined) headers.set("Content-Type", "application/json");
    const response = await fetch(url, {
      method, headers, ...(body === undefined ? {} : {body}), mode: "cors",
      credentials: "omit", redirect: "error", cache: "no-store", referrerPolicy: "no-referrer",
    });
    if (!response.ok || response.headers.get("Content-Type") !== "application/json") throw new Error("Request failed.");
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
    /** @type {Map<string, {path:string, method:"GET" | "POST", operation:string}>} */ const calls = new Map();
    /** @type {unknown[]} */ const entries = data.calls;
    for (const item of entries) {
      if (object(item) && typeof item.id === "string" && typeof item.path === "string" && item.identity === null
        && ((item.method === "GET" && item.operation === "read") || (item.method === "POST" && item.operation === "check"))) {
        calls.set(item.id, {path:item.path, method:item.method, operation:item.operation});
      }
    }
    /** @param {string} id @param {"GET" | "POST"} method @param {unknown} body */
    async function run(id, method, body) {
      try {
        const call = calls.get(id);
        if (!call || call.method !== method) throw new Error("Request refused.");
        const response = await send(call.path, method, method === "GET" ? undefined : JSON.stringify(body), false);
        /** @type {unknown} */ const value = await response.json();
        return value;
      } catch { throw new Error("Request failed."); }
    }
    return Object.freeze({
      /** @param {string} id */ read: (id) => run(id, "GET", undefined),
      /** @param {string} id @param {unknown} body */ check: (id, body) => run(id, "POST", body),
    });
  } catch { throw new Error("Request failed."); }
}
