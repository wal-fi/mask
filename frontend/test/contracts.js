/** @type {ReadonlyArray<import("../private/contracts.js").UiWriteContract>} */
export const allowed = [
  {method:"POST",path:"/admin/v1/config:adopt",request:{expected_revision:0,confirm_comment_loss:true},response:{revision:1,applied:true}},
  {method:"POST",path:"/admin/v1/rules:reorder",request:{expected_revision:1,rule_ids:[]},response:{revision:2,applied:true}},
  {method:"POST",path:"/admin/v1/rules",request:{expected_revision:1,rule:{match:"x",transformer:"fixed",config:{value:"hidden"}}},response:{revision:2,applied:true}},
  {method:"PUT",path:"/admin/v1/rules/{rule_id}",request:{expected_revision:1,rule:{match:"x",transformer:"random",config:{strategy:"digits",preserve_length:false,length:0}}},response:{revision:2,applied:true}},
  {method:"DELETE",path:"/admin/v1/rules/{rule_id}",request:{expected_revision:1},response:{revision:2,applied:true}},
  {method:"POST",path:"/admin/v1/exceptions",request:{expected_revision:1,exception:{match:"x"}},response:{revision:2,applied:true}},
  {method:"PUT",path:"/admin/v1/exceptions/{exception_id}",request:{expected_revision:1,exception:{match:"x"}},response:{revision:2,applied:true}},
  {method:"DELETE",path:"/admin/v1/exceptions/{exception_id}",request:{expected_revision:1},response:{revision:2,applied:true}},
  {method:"PUT",path:"/admin/v1/database",request:{expected_revision:1,statement_timeout_ms:100,max_rows:1},response:{revision:2,applied:true}},
  {method:"PUT",path:"/admin/v1/sql",request:{expected_revision:1,denied_functions:["blocked"]},response:{revision:2,applied:true}},
];
/** @type {import("../private/contracts.js").WriteContract} */
export const full = {method:"PUT",path:"/admin/v1/config",request:{expected_revision:1,masking:[],exceptions:[],database:{statement_timeout_ms:100,max_rows:1},sql:{denied_functions:[]}},response:{revision:2,applied:true}};

/** @type {import("../private/contracts.js").WriteOutcome} */
export const uncertain = {type:"uncertain",value:{error:"CONFIG_DURABILITY_ERROR",detail:"Durabilidade não confirmada.",applied:true,current_revision:2}};
/** @type {import("../private/contracts.js").ViewState} */
export const uncertainView = {type:"uncertain",value:{error:"CONFIG_DURABILITY_ERROR",detail:"Durabilidade não confirmada.",applied:true,current_revision:2}};
