# DSL Specification for Trading Strategy Rules

## 1. Overview
This Domain-Specific Language (DSL) defines trading strategy rules for entry and exit 
conditions using OHLCV market data. The DSL supports comparisons, logical operators, 
indicators (SMA, RSI), cross events, and time-based references.

## 2. Lexical Elements

Type | Examples 

Identifier | open, high, low, close, volume 
Numeric literal | 100, 1000000, 20 
Keywords | ENTRY, EXIT, AND, OR 
Comparison operators | >, <, >=, <=, == 
Indicator functions | SMA(x, N), RSI(x, N) 
Cross functions | CROSS_ABOVE(x, y), CROSS_BELOW(x, y) 
Parentheses | ( ) 

## 3. Grammar (BNF-style)

<strategy> ::= ENTRY ":" <expr_list> NEWLINE EXIT ":" <expr_list>

<expr_list> ::= <expr> ( ( "AND" | "OR" ) <expr> )*

<expr> ::= <comparison>
         | <cross_expr>
         | "(" <expr_list> ")"

<comparison> ::= <value> <comp_op> <value>

<value> ::= <series>
          | <indicator>
          | <number>

<series> ::= "open" | "high" | "low" | "close" | "volume"

<indicator> ::= "SMA" "(" <series> "," <number> ")"
              | "RSI" "(" <series> "," <number> ")"

<cross_expr> ::= "CROSS_ABOVE" "(" <series> "," <indicator> ")"
                | "CROSS_BELOW" "(" <series> "," <indicator> ")"

<comp_op> ::= ">" | "<" | ">=" | "<=" | "=="

## 4. Indicator Semantics

### SMA
SMA(x, n) = rolling mean of series x with window n.

### RSI
Uses standard Wilder’s RSI formula.

## 5. Cross Semantics

### CROSS_ABOVE(A, B)
A cross above occurs when:
A[t-1] <= B[t-1] AND A[t] > B[t]

### CROSS_BELOW(A, B)
A cross below occurs when:
A[t-1] >= B[t-1] AND A[t] < B[t]

## 6. Time-Based Reference Semantics

Natural Language | DSL Mapping

"yesterday" | series.shift(1)
"N-day moving average" | SMA(series, N)
"last week" | 5-period window

## 7. Validation Rules

Unknown identifiers must throw errors  
Incorrect indicator syntax must throw errors  
Parentheses must be balanced  
Comparison operations require valid operands  
Only supported keywords may be used  

## 8. DSL Examples

### Example 1
ENTRY: close > SMA(close,20) AND volume > 1000000  
EXIT: RSI(close,14) < 30

### Example 2
ENTRY: CROSS_ABOVE(close, high)  
EXIT: RSI(close,14) < 70

### Example 3
ENTRY: close > SMA(close,20)  
EXIT: RSI(close,14) < 30

## 9. Assumptions

Only assignment-style English input is supported  
No nested indicators for simplicity  
Missing rolling window values produce "False" signals  
DSL is case-insensitive for keywords  

