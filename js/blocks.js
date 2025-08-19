/* ---------- CONSTANTS --------------------------------------------------- */
const columns = [
  'Time','Open','High','Low','Close','Volume','Close_time',
  'Quote_asset_volume','Number_of_trades',
  'Taker_buy_base_asset_volume','Taker_buy_quote_asset_volume'
];
const globals_values = {};

/* ---------- TOOLBOX ----------------------------------------------------- */
const toolbox = {
  kind: 'categoryToolbox',
  contents: [
    /* Values */
    { kind:'category', name:'Values', colour:230, contents:[
        {kind:'block', type:'column_value'},
        {kind:'block', type:'math_number'},
        {kind:'block', type:'balance_initial'},
        {kind:'block', type:'globals_values_set'},
        {kind:'block', type:'globals_values_get'},
        {kind:'block', type:'globals_values_create'}
    ]},

    /* Logic */
    { kind:'category', name:'Logic', colour:210, contents:[
        {kind:'block', type:'logic_compare'},
        {kind:'block', type:'logic_operation'},
        {kind:'block', type:'controls_if'}
    ]},

    /* Loops */
    { kind:'category', name:'Loops', colour:120, contents:[
        {kind:'block', type:'controls_for'},
        {kind:'block', type:'controls_repeat_ext'}
    ]},

    /* Functions */
    { kind:'category', name:'Functions', colour:290, custom:'PROCEDURE' },

    /* Indicators */
    { kind:'category', name:'Indicators', colour:260, contents:[
        {kind:'block', type:'sma_indicator'},
        {kind:'block', type:'macd_indicator'},
        {kind:'block', type:'bb_upper_indicator'},
        {kind:'block', type:'bb_middle_indicator'},
        {kind:'block', type:'bb_lower_indicator'},
        {kind:'block', type:'supertrend_up_indicator'}
    ]},

    /* Action */
    { kind:'category', name:'Action', colour:120, contents:[
        {kind:'block', type:'buy_action'},
        {kind:'block', type:'sell_action'},
        {kind:'block', type:'close_position_action'},    /* NEW */
        {kind:'block', type:'log_action'},
        {kind:'block', type:'grid_orders'},
        {kind:'block', type:'take_profit_action'}
    ]}
  ]
};

/* ---------- CUSTOM BLOCKS ---------------------------------------------- */
Blockly.defineBlocksWithJsonArray([
  /* ----- Values & Indicators ------------------------------------------- */
  { type:'column_value', output:'Number',
    message0:'%1',
    args0:[{type:'field_dropdown', name:'COL', options:columns.map(c=>[c,c])}],
    colour:230 },

  { type:'balance_initial', output:'Boolean',
    message0:'Balance == initial',
    colour:230 },

  { type:'sma_indicator', output:'Number',
    message0:'SMA %1 of %2',
    args0:[
      {type:'field_dropdown', name:'COL', options:columns.map(c=>[c,c])},
      {type:'field_number', name:'PER', value:14, min:1}
    ],
    colour:260 },

  { type:'macd_indicator', output:'Number',
    message0:'MACD %1 fast %2 slow %3',
    args0:[
      {type:'field_dropdown', name:'COL', options:columns.map(c=>[c,c])},
      {type:'field_number', name:'FAST', value:12, min:1},
      {type:'field_number', name:'SLOW', value:26, min:1}
    ],
    colour:260 },

  { type:'bb_upper_indicator', output:'Number',
    message0:'BB upper %1 period %2 mult %3',
    args0:[
      {type:'field_dropdown', name:'COL', options:columns.map(c=>[c,c])},
      {type:'field_number', name:'PER', value:20, min:1},
      {type:'field_number', name:'MULT', value:2,  min:0}
    ],
    colour:260 },

  { type:'bb_middle_indicator', output:'Number',
    message0:'BB middle %1 period %2 mult %3',
    args0:[
      {type:'field_dropdown', name:'COL', options:columns.map(c=>[c,c])},
      {type:'field_number', name:'PER', value:20, min:1},
      {type:'field_number', name:'MULT', value:2,  min:0}
    ],
    colour:260 },

  { type:'bb_lower_indicator', output:'Number',
    message0:'BB lower %1 period %2 mult %3',
    args0:[
      {type:'field_dropdown', name:'COL', options:columns.map(c=>[c,c])},
      {type:'field_number', name:'PER', value:20, min:1},
      {type:'field_number', name:'MULT', value:2,  min:0}
    ],
    colour:260 },

  /* ----- Supertrend (Boolean) ------------------------------------------ */
  { type:'supertrend_up_indicator', output:'Boolean',
    message0:'Supertrend up ATR %1 factor %2',
    args0:[
      {type:'field_number', name:'PER',    value:10, min:1},
      {type:'field_number', name:'FACTOR', value:3,  min:0.01, precision:0.01}
    ],
    colour:260 },

  /* ----- Actions & Globals --------------------------------------------- */
  { type:'buy_action',
    message0:'BUY %1',
    args0:[{type:'input_value', name:'AMT', check:'Number'}],
    previousStatement:null, nextStatement:null, colour:120 },

  { type:'sell_action',
    message0:'SELL %1',
    args0:[{type:'input_value', name:'AMT', check:'Number'}],
    previousStatement:null, nextStatement:null, colour:300 },

  /* NEW: Close position immediately ------------------------------------- */
  { type:'close_position_action',
    message0:'CLOSE position',
    previousStatement:null, nextStatement:null, colour:0 },

  { type:'log_action',
    message0:'LOG %1',
    args0:[{type:'input_value', name:'AMT'}],
    previousStatement:null, nextStatement:null, colour:300 },

  { type:'globals_values_set',
    message0:'globals values set %1 %2',
    args0:[
      {type:'input_value', name:'VALUE'},
      {type:'field_dropdown', name:'KEY', options:()=> {
        const k = Object.keys(globals_values);
        return k.length ? k.map(x=>[x,x]) : [['','']];
      }}
    ],
    previousStatement:null, nextStatement:null, colour:300 },

  { type:'globals_values_get', output:'Number',
    message0:'globals values get %1',
    args0:[
      {type:'field_dropdown', name:'KEY', options:()=> {
        const k = Object.keys(globals_values);
        return k.length ? k.map(x=>[x,x]) : [['','']];
      }}
    ],
    colour:300 },

  { type:'globals_values_create', output:'*',
    message0:'globals values create %1',
    args0:[{type:'field_input', name:'KEY', text:''}],
    colour:300 },

  /* ----- Grid Orders ---------------------------------------------------- */
  { type:'grid_orders',
    message0:'GRID orders %1 factor %2 step %3 price %4',
    args0:[
      {type:'field_number', name:'COUNT',  value:20,  min:0},
      {type:'field_number', name:'FACTOR', value:0.1, min:0},
      {type:'field_number', name:'STEP',   value:1.2, min:0},
      {type:'input_value',  name:'PRICE',  check:'Number'}
    ],
    previousStatement:null, nextStatement:null, colour:120 },

  /* ----- Take-Profit ---------------------------------------------------- */
  { type:'take_profit_action',
    message0:'TAKE profit %1 %%',
    args0:[{type:'field_number', name:'PCT', value:5, min:0}],
    previousStatement:null, nextStatement:null, colour:300 }
]);

/* ---------- GENERATORS -------------------------------------------------- */
Blockly.JavaScript['column_value']  = b=>[`Number(row['${b.getFieldValue('COL')}'])`,Blockly.JavaScript.ORDER_ATOMIC];
Blockly.JavaScript['balance_initial']=b=>[`isBalanceInitial()`,Blockly.JavaScript.ORDER_ATOMIC];
Blockly.JavaScript['sma_indicator'] = b=>[`computeSMA(data,'${b.getFieldValue('COL')}',${b.getFieldValue('PER')},idx)`,Blockly.JavaScript.ORDER_ATOMIC];
Blockly.JavaScript['macd_indicator']= b=>[`computeMACD(data,'${b.getFieldValue('COL')}',${b.getFieldValue('FAST')},${b.getFieldValue('SLOW')},idx)`,Blockly.JavaScript.ORDER_ATOMIC];
Blockly.JavaScript['bb_upper_indicator']  = b=>[`computeBBUpper(data,'${b.getFieldValue('COL')}',${b.getFieldValue('PER')},${b.getFieldValue('MULT')},idx)`,Blockly.JavaScript.ORDER_ATOMIC];
Blockly.JavaScript['bb_middle_indicator'] = b=>[`computeBBMiddle(data,'${b.getFieldValue('COL')}',${b.getFieldValue('PER')},${b.getFieldValue('MULT')},idx)`,Blockly.JavaScript.ORDER_ATOMIC];
Blockly.JavaScript['bb_lower_indicator']  = b=>[`computeBBLower(data,'${b.getFieldValue('COL')}',${b.getFieldValue('PER')},${b.getFieldValue('MULT')},idx)`,Blockly.JavaScript.ORDER_ATOMIC];
Blockly.JavaScript['supertrend_up_indicator']=b=>[
  `computeSupertrendUp(data,${b.getFieldValue('PER')},${b.getFieldValue('FACTOR')},idx)`,
  Blockly.JavaScript.ORDER_ATOMIC
];

Blockly.JavaScript['buy_action']  = b=>{
  const v=Blockly.JavaScript.valueToCode(b,'AMT',Blockly.JavaScript.ORDER_NONE)||'0';
  return`buy(${v});\n`;
};
Blockly.JavaScript['sell_action'] = b=>{
  const v=Blockly.JavaScript.valueToCode(b,'AMT',Blockly.JavaScript.ORDER_NONE)||'0';
  return`sell(${v});\n`;
};
Blockly.JavaScript['close_position_action']=b=>'closePosition();\n';
Blockly.JavaScript['log_action']  = b=>{
  const v=Blockly.JavaScript.valueToCode(b,'AMT',Blockly.JavaScript.ORDER_NONE)||'""';
  return`log(${v});\n`;
};
Blockly.JavaScript['globals_values_set']=b=>{
  const k=b.getFieldValue('KEY');
  const v=Blockly.JavaScript.valueToCode(b,'VALUE',Blockly.JavaScript.ORDER_NONE)||'null';
  return`globals_values_set('${k}',${v});\n`;
};
Blockly.JavaScript['globals_values_get']=b=>[`globals_values_get('${b.getFieldValue('KEY')}')`,Blockly.JavaScript.ORDER_ATOMIC];
Blockly.JavaScript['globals_values_create']=b=>[`globals_values_create('${b.getFieldValue('KEY')}')`,Blockly.JavaScript.ORDER_ATOMIC];
Blockly.JavaScript['grid_orders']=b=>{
  const c=b.getFieldValue('COUNT');
  const f=b.getFieldValue('FACTOR');
  const s=b.getFieldValue('STEP');
  const p=Blockly.JavaScript.valueToCode(b,'PRICE',Blockly.JavaScript.ORDER_NONE)||'0';
  return`placeGridOrders(${c},${f},${s},${p});\n`;
};
Blockly.JavaScript['take_profit_action']=b=>{
  const p=b.getFieldValue('PCT');
  return`setTakeProfit(${p});\n`;
};

