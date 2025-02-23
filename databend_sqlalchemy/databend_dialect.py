#!/usr/bin/env python
#
# Note: parts of the file come from https://github.com/snowflakedb/snowflake-sqlalchemy
#       licensed under the same Apache 2.0 License

"""
Databend Table Options
------------------------

Several options for CREATE TABLE are supported directly by the Databend
dialect in conjunction with the :class:`_schema.Table` construct:

* ``ENGINE``::

    Table("some_table", metadata, ..., databend_engine=FUSE|Memory|Random|Iceberg|Delta)

* ``CLUSTER KEY``::

    Table("some_table", metadata, ..., databend_cluster_by=str|LIST(expr|str))

* ``TRANSIENT``::

    Table("some_table", metadata, ..., databend_transient=True|False)

"""

import decimal
import re
import operator
import datetime
import sqlalchemy.types as sqltypes
from typing import Any, Dict, Optional, Union
from sqlalchemy import util as sa_util
from sqlalchemy.engine import reflection
from sqlalchemy.sql import (
    compiler,
    text,
    bindparam,
    select,
    TableClause,
    Select,
    Subquery,
)
from sqlalchemy.dialects.postgresql.base import PGCompiler, PGIdentifierPreparer
from sqlalchemy.types import (
    BIGINT,
    INTEGER,
    SMALLINT,
    DECIMAL,
    NUMERIC,
    VARCHAR,
    BINARY,
    BOOLEAN,
    FLOAT,
    JSON,
    CHAR,
    TIMESTAMP,
)
from sqlalchemy.engine import ExecutionContext, default
from sqlalchemy.exc import DBAPIError, NoSuchTableError

from .dml import Merge
from .types import INTERVAL

RESERVED_WORDS = {
    "Error",
    "EOI",
    "Whitespace",
    "Comment",
    "CommentBlock",
    "Ident",
    "ColumnPosition",
    "LiteralString",
    "LiteralCodeString",
    "LiteralAtString",
    "PGLiteralHex",
    "MySQLLiteralHex",
    "LiteralInteger",
    "LiteralFloat",
    "HintPrefix",
    "HintSuffix",
    "DoubleEq",
    "Eq",
    "NotEq",
    "Lt",
    "Gt",
    "Lte",
    "Gte",
    "Spaceship",
    "Plus",
    "Minus",
    "Multiply",
    "Divide",
    "IntDiv",
    "Modulo",
    "StringConcat",
    "LParen",
    "RParen",
    "Comma",
    "Dot",
    "Colon",
    "DoubleColon",
    "ColonEqual",
    "SemiColon",
    "Backslash",
    "LBracket",
    "RBracket",
    "Caret",
    "LBrace",
    "RBrace",
    "RArrow",
    "LongRArrow",
    "FatRArrow",
    "HashRArrow",
    "HashLongRArrow",
    "TildeAsterisk",
    "ExclamationMarkTilde",
    "ExclamationMarkTildeAsterisk",
    "BitWiseAnd",
    "BitWiseOr",
    "BitWiseXor",
    "BitWiseNot",
    "ShiftLeft",
    "ShiftRight",
    "Factorial",
    "DoubleExclamationMark",
    "Abs",
    "SquareRoot",
    "CubeRoot",
    "Placeholder",
    "QuestionOr",
    "QuestionAnd",
    "ArrowAt",
    "AtArrow",
    "AtQuestion",
    "AtAt",
    "HashMinus",
    "ACCOUNT",
    "ALL",
    "ALLOWED_IP_LIST",
    "ADD",
    "AFTER",
    "AGGREGATING",
    "ANY",
    "APPEND_ONLY",
    "ARGS",
    "AUTO",
    "SOME",
    "ALTER",
    "ALWAYS",
    "ANALYZE",
    "AND",
    "ARRAY",
    "AS",
    "AST",
    "AT",
    "ASC",
    "ANTI",
    "ASYNC",
    "ATTACH",
    "BEFORE",
    "BETWEEN",
    "BIGINT",
    "BINARY",
    "BREAK",
    "LONGBLOB",
    "MEDIUMBLOB",
    "TINYBLOB",
    "BLOB",
    "BINARY_FORMAT",
    "BITMAP",
    "BLOCKED_IP_LIST",
    "BOOL",
    "BOOLEAN",
    "BOTH",
    "BY",
    "BROTLI",
    "BZ2",
    "CALL",
    "CASE",
    "CAST",
    "CATALOG",
    "CATALOGS",
    "CENTURY",
    "CHANGES",
    "CLUSTER",
    "COMMENT",
    "COMMENTS",
    "COMPACT",
    "CONNECTION",
    "CONNECTIONS",
    "CONSUME",
    "CONTENT_TYPE",
    "CONTINUE",
    "CHAR",
    "COLUMN",
    "COLUMNS",
    "CHARACTER",
    "CONFLICT",
    "COMPRESSION",
    "COPY_OPTIONS",
    "COPY",
    "COUNT",
    "CREDENTIAL",
    "CREATE",
    "CROSS",
    "CSV",
    "CURRENT",
    "CURRENT_TIMESTAMP",
    "DATABASE",
    "DATABASES",
    "DATA",
    "DATE",
    "DATE_ADD",
    "DATE_PART",
    "DATE_SUB",
    "DATE_TRUNC",
    "DATETIME",
    "DAY",
    "DECADE",
    "DECIMAL",
    "DECLARE",
    "DEFAULT",
    "DEFLATE",
    "DELETE",
    "DESC",
    "DETAILED_OUTPUT",
    "DESCRIBE",
    "DISABLE",
    "DISABLE_VARIANT_CHECK",
    "DISTINCT",
    "RESPECT",
    "IGNORE",
    "DIV",
    "DOUBLE_SHA1_PASSWORD",
    "DO",
    "DOUBLE",
    "DOW",
    "WEEK",
    "DELTA",
    "DOY",
    "DOWNLOAD",
    "DOWNSTREAM",
    "DROP",
    "DRY",
    "DYNAMIC",
    "EXCEPT",
    "EXCLUDE",
    "ELSE",
    "EMPTY_FIELD_AS",
    "ENABLE",
    "ENABLE_VIRTUAL_HOST_STYLE",
    "END",
    "ENDPOINT",
    "ENGINE",
    "ENGINES",
    "EPOCH",
    "ERROR_ON_COLUMN_COUNT_MISMATCH",
    "ESCAPE",
    "EXCEPTION_BACKTRACE",
    "EXISTS",
    "EXPLAIN",
    "EXPIRE",
    "EXTRACT",
    "ELSEIF",
    "FALSE",
    "FIELDS",
    "FIELD_DELIMITER",
    "NAN_DISPLAY",
    "NULL_DISPLAY",
    "NULL_IF",
    "FILE_FORMAT",
    "FILE",
    "FILES",
    "FINAL",
    "FLASHBACK",
    "FLOAT",
    "FLOAT32",
    "FLOAT64",
    "FOR",
    "FORCE",
    "FORMAT",
    "FOLLOWING",
    "FORMAT_NAME",
    "FORMATS",
    "FRAGMENTS",
    "FROM",
    "FULL",
    "FUNCTION",
    "FUNCTIONS",
    "TABLE_FUNCTIONS",
    "SET_VAR",
    "FUSE",
    "GET",
    "GENERATED",
    "GEOMETRY",
    "GLOBAL",
    "GRAPH",
    "GROUP",
    "GZIP",
    "HAVING",
    "HIGH",
    "HISTORY",
    "HIVE",
    "HOUR",
    "HOURS",
    "ICEBERG",
    "INTERSECT",
    "IDENTIFIED",
    "IDENTIFIER",
    "IF",
    "IN",
    "INCREMENTAL",
    "INDEX",
    "INFORMATION",
    "INITIALIZE",
    "INNER",
    "INSERT",
    "INT",
    "INT16",
    "INT32",
    "INT64",
    "INT8",
    "INTEGER",
    "INTERVAL",
    "INTO",
    "INVERTED",
    "IMMEDIATE",
    "IS",
    "ISODOW",
    "ISOYEAR",
    "JOIN",
    "JSON",
    "JULIAN",
    "JWT",
    "KEY",
    "KILL",
    "LATERAL",
    "LOCATION_PREFIX",
    "LOCKS",
    "LOGICAL",
    "LOOP",
    "SECONDARY",
    "ROLES",
    "L2DISTANCE",
    "LEADING",
    "LEFT",
    "LET",
    "LIKE",
    "LIMIT",
    "LIST",
    "LOW",
    "LZO",
    "MASKING",
    "MAP",
    "MAX_FILE_SIZE",
    "MASTER_KEY",
    "MEDIUM",
    "MEMO",
    "MEMORY",
    "METRICS",
    "MICROSECONDS",
    "MILLENNIUM",
    "MILLISECONDS",
    "MINUTE",
    "MONTH",
    "MODIFY",
    "MATERIALIZED",
    "MUST_CHANGE_PASSWORD",
    "NON_DISPLAY",
    "NATURAL",
    "NETWORK",
    "DISABLED",
    "NDJSON",
    "NO_PASSWORD",
    "NONE",
    "NOT",
    "NOTENANTSETTING",
    "DEFAULT_ROLE",
    "NULL",
    "NULLABLE",
    "OBJECT",
    "OF",
    "OFFSET",
    "ON",
    "ON_CREATE",
    "ON_SCHEDULE",
    "OPTIMIZE",
    "OPTIONS",
    "OR",
    "ORC",
    "ORDER",
    "OUTPUT_HEADER",
    "OUTER",
    "ON_ERROR",
    "OVER",
    "OVERWRITE",
    "PARTITION",
    "PARQUET",
    "PASSWORD",
    "PASSWORD_MIN_LENGTH",
    "PASSWORD_MAX_LENGTH",
    "PASSWORD_MIN_UPPER_CASE_CHARS",
    "PASSWORD_MIN_LOWER_CASE_CHARS",
    "PASSWORD_MIN_NUMERIC_CHARS",
    "PASSWORD_MIN_SPECIAL_CHARS",
    "PASSWORD_MIN_AGE_DAYS",
    "PASSWORD_MAX_AGE_DAYS",
    "PASSWORD_MAX_RETRIES",
    "PASSWORD_LOCKOUT_TIME_MINS",
    "PASSWORD_HISTORY",
    "PATTERN",
    "PIPELINE",
    "PLAINTEXT_PASSWORD",
    "POLICIES",
    "POLICY",
    "POSITION",
    "PROCESSLIST",
    "PRIORITY",
    "PURGE",
    "PUT",
    "QUARTER",
    "QUERY",
    "QUOTE",
    "RANGE",
    "RAWDEFLATE",
    "READ_ONLY",
    "RECLUSTER",
    "RECORD_DELIMITER",
    "REFERENCE_USAGE",
    "REFRESH",
    "REGEXP",
    "RENAME",
    "REPLACE",
    "RETURN_FAILED_ONLY",
    "REVERSE",
    "MERGE",
    "MATCHED",
    "MISSING_FIELD_AS",
    "NULL_FIELD_AS",
    "UNMATCHED",
    "ROW",
    "ROWS",
    "ROW_TAG",
    "GRANT",
    "REPEAT",
    "ROLE",
    "PRECEDING",
    "PRECISION",
    "PRESIGN",
    "PRIVILEGES",
    "QUALIFY",
    "REMOVE",
    "RETAIN",
    "REVOKE",
    "RECURSIVE",
    "RETURN",
    "RETURNS",
    "RESULTSET",
    "RUN",
    "GRANTS",
    "REFRESH_MODE",
    "RIGHT",
    "RLIKE",
    "RAW",
    "OPTIMIZED",
    "SCHEMA",
    "SCHEMAS",
    "SECOND",
    "MILLISECOND",
    "SELECT",
    "PIVOT",
    "UNPIVOT",
    "SEGMENT",
    "SET",
    "UNSET",
    "SESSION",
    "SETTINGS",
    "STAGES",
    "STATISTIC",
    "SUMMARY",
    "SHA256_PASSWORD",
    "SHOW",
    "SINCE",
    "SIGNED",
    "SINGLE",
    "SIZE_LIMIT",
    "MAX_FILES",
    "SKIP_HEADER",
    "SMALLINT",
    "SNAPPY",
    "SNAPSHOT",
    "SPLIT_SIZE",
    "STAGE",
    "SYNTAX",
    "USAGE",
    "UPDATE",
    "UPLOAD",
    "SEQUENCE",
    "SHARE",
    "SHARES",
    "SUPER",
    "STATUS",
    "STORED",
    "STREAM",
    "STREAMS",
    "STRING",
    "SUBSTRING",
    "SUBSTR",
    "SEMI",
    "SOUNDS",
    "SYNC",
    "SYSTEM",
    "STORAGE_TYPE",
    "TABLE",
    "TABLES",
    "TARGET_LAG",
    "TEXT",
    "LONGTEXT",
    "MEDIUMTEXT",
    "TINYTEXT",
    "TENANTSETTING",
    "TENANTS",
    "TENANT",
    "THEN",
    "TIMESTAMP",
    "TIMEZONE_HOUR",
    "TIMEZONE_MINUTE",
    "TIMEZONE",
    "TINYINT",
    "TO",
    "TOKEN",
    "TRAILING",
    "TRANSIENT",
    "TRIM",
    "TRUE",
    "TRUNCATE",
    "TRY_CAST",
    "TSV",
    "TUPLE",
    "TYPE",
    "UNBOUNDED",
    "UNION",
    "UINT16",
    "UINT32",
    "UINT64",
    "UINT8",
    "UNDROP",
    "UNSIGNED",
    "URL",
    "METHOD",
    "AUTHORIZATION_HEADER",
    "USE",
    "USER",
    "USERS",
    "USING",
    "VACUUM",
    "VALUES",
    "VALIDATION_MODE",
    "VARBINARY",
    "VARCHAR",
    "VARIANT",
    "VERBOSE",
    "VIEW",
    "VIEWS",
    "VIRTUAL",
    "WHEN",
    "WHERE",
    "WHILE",
    "WINDOW",
    "WITH",
    "XML",
    "XOR",
    "XZ",
    "YEAR",
    "ZSTD",
    "NULLIF",
    "COALESCE",
    "RANDOM",
    "IFNULL",
    "NULLS",
    "FIRST",
    "LAST",
    "IGNORE_RESULT",
    "GROUPING",
    "SETS",
    "CUBE",
    "ROLLUP",
    "INDEXES",
    "ADDRESS",
    "OWNERSHIP",
    "READ",
    "WRITE",
    "UDF",
    "HANDLER",
    "LANGUAGE",
    "TASK",
    "TASKS",
    "TOP",
    "WAREHOUSE",
    "SCHEDULE",
    "SUSPEND_TASK_AFTER_NUM_FAILURES",
    "CRON",
    "EXECUTE",
    "SUSPEND",
    "RESUME",
    "PIPE",
    "NOTIFICATION",
    "INTEGRATION",
    "ENABLED",
    "WEBHOOK",
    "ERROR_INTEGRATION",
    "AUTO_INGEST",
    "PIPE_EXECUTION_PAUSED",
    "PREFIX",
    "MODIFIED_AFTER",
    "UNTIL",
    "BEGIN",
    "TRANSACTION",
    "COMMIT",
    "ABORT",
    "ROLLBACK",
    "TEMPORARY",
    "SECONDS",
    "DAYS",
}


# Type decorators
class ARRAY(sqltypes.TypeEngine):
    __visit_name__ = "ARRAY"


class MAP(sqltypes.TypeEngine):
    __visit_name__ = "MAP"

    def __init__(self, key_type, value_type):
        self.key_type = key_type
        self.value_type = value_type
        super(MAP, self).__init__()


class DatabendDate(sqltypes.DATE):
    __visit_name__ = "DATE"

    _reg = re.compile(r"(\d+)-(\d+)-(\d+)")

    def result_processor(self, dialect, coltype):
        def process(value):
            if isinstance(value, str):
                m = self._reg.match(value)
                if not m:
                    raise ValueError("could not parse %r as a date value" % (value,))
                return datetime.date(*[int(x or 0) for x in m.groups()])
            else:
                return value

        return process


class DatabendDateTime(sqltypes.DATETIME):
    __visit_name__ = "DATETIME"

    _reg = re.compile(r"(\d+)-(\d+)-(\d+) (\d+):(\d+):(\d+)")

    def result_processor(self, dialect, coltype):
        def process(value):
            if isinstance(value, str):
                m = self._reg.match(value)
                if not m:
                    raise ValueError(
                        "could not parse %r as a datetime value" % (value,)
                    )
                return datetime.datetime(*[int(x or 0) for x in m.groups()])
            else:
                return value

        return process

    def literal_processor(self, dialect):
        def process(value):
            if value is not None:
                datetime_str = value.isoformat(" ", timespec="microseconds")
                return f"'{datetime_str}'"

        return process


class DatabendTime(sqltypes.TIME):
    __visit_name__ = "TIME"

    _reg = re.compile(r"(?:\d+)-(?:\d+)-(?:\d+) (\d+):(\d+):(\d+)")

    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return None
            if isinstance(value, str):
                m = self._reg.match(value)
                if not m:
                    raise ValueError(
                        "could not parse %r as a datetime value" % (value,)
                    )
                return datetime.time(*[int(x or 0) for x in m.groups()])
            else:
                return value.time()

        return process

    def literal_processor(self, dialect):
        def process(value):
            if value is not None:
                from_min_value = datetime.datetime.combine(
                    datetime.date(1000, 1, 1), value
                )
                time_str = from_min_value.isoformat(timespec="microseconds")
                return f"'{time_str}'"

        return process


class DatabendNumeric(sqltypes.Numeric):
    def result_processor(self, dialect, type_):
        orig = super().result_processor(dialect, type_)

        def process(value):
            if value is not None:
                if self.decimal_return_scale:
                    value = decimal.Decimal(f"{value:.{self.decimal_return_scale}f}")
                else:
                    value = decimal.Decimal(value)
            if orig:
                return orig(value)
            return value

        return process


class DatabendInterval(INTERVAL):
    render_bind_cast = True


# Type converters
ischema_names = {
    "bigint": BIGINT,
    "int": INTEGER,
    "smallint": SMALLINT,
    "tinyint": SMALLINT,
    "int64": BIGINT,
    "int32": INTEGER,
    "int16": SMALLINT,
    "int8": SMALLINT,
    "uint64": BIGINT,
    "uint32": INTEGER,
    "uint16": SMALLINT,
    "uint8": SMALLINT,
    "numeric": NUMERIC,
    "decimal": DECIMAL,
    "date": DatabendDate,
    "datetime": DatabendDateTime,
    "timestamp": DatabendDateTime,
    "float": FLOAT,
    "double": FLOAT,
    "float64": FLOAT,
    "float32": FLOAT,
    "string": VARCHAR,
    "array": ARRAY,
    "map": MAP,
    "json": JSON,
    "variant": JSON,
    "varchar": VARCHAR,
    "boolean": BOOLEAN,
    "binary": BINARY,
    "time": DatabendTime,
    "interval": DatabendInterval,
}

# Column spec
colspecs = {
    sqltypes.Interval: DatabendInterval,
    sqltypes.Time: DatabendTime,
    sqltypes.Date: DatabendDate,
    sqltypes.DateTime: DatabendDateTime,
    sqltypes.DECIMAL: DatabendNumeric,
    sqltypes.Numeric: DatabendNumeric,
}


class DatabendIdentifierPreparer(PGIdentifierPreparer):
    reserved_words = {r.lower() for r in RESERVED_WORDS}


class DatabendCompiler(PGCompiler):
    def get_select_precolumns(self, select, **kw):
        # call the base implementation because Databend doesn't support DISTINCT ON
        return super(PGCompiler, self).get_select_precolumns(select, **kw)

    def visit_count_func(self, fn, **kw):
        return "count{0}".format(self.process(fn.clause_expr, **kw))

    def visit_random_func(self, fn, **kw):
        return "rand()"

    def visit_now_func(self, fn, **kw):
        return "now()"

    def visit_current_date_func(self, fn, **kw):
        return "today()"

    def visit_cast(self, cast, **kwargs):
        if self.dialect.supports_cast:
            return super(DatabendCompiler, self).visit_cast(cast, **kwargs)
        else:
            return self.process(cast.clause, **kwargs)

    def visit_substring_func(self, func, **kw):
        s = self.process(func.clauses.clauses[0], **kw)
        start = self.process(func.clauses.clauses[1], **kw)
        if len(func.clauses.clauses) > 2:
            length = self.process(func.clauses.clauses[2], **kw)
            return "substring(%s, %s, %s)" % (s, start, length)
        else:
            return "substring(%s, %s)" % (s, start)

    def visit_concat_op_binary(self, binary, operator, **kw):
        return "concat(%s, %s)" % (
            self.process(binary.left),
            self.process(binary.right),
        )

    def render_literal_value(self, value, type_):
        value = super(DatabendCompiler, self).render_literal_value(value, type_)
        # if isinstance(type_, sqltypes.DateTime):
        #     return "to_datetime(%s)" % value
        # if isinstance(type_, sqltypes.Date):
        #     return "to_date(%s)" % value
        # if isinstance(type_, sqltypes.Time):
        #     return "to_datetime(%s)" % value
        # if isinstance(type_, sqltypes.Interval):
        #     return "to_datetime(%s)" % value
        return value

    def limit_clause(self, select, **kw):
        text = ""
        if select._limit_clause is not None:
            text += " \n LIMIT " + self.process(select._limit_clause, **kw)
        if select._offset_clause is not None:
            if select._limit_clause is None:
                text += "\n"
            text += " OFFSET " + self.process(select._offset_clause, **kw)
        return text

    def for_update_clause(self, select, **kw):
        return ""  # Not supported

    def visit_like_op_binary(self, binary, operator, **kw):
        # escape = binary.modifiers.get("escape", None)
        return "%s LIKE %s" % (
            binary.left._compiler_dispatch(self, **kw),
            binary.right._compiler_dispatch(self, **kw),
            # ToDo - escape not yet supported
            # ) + (
            #     " ESCAPE " + self.render_literal_value(escape, sqltypes.STRINGTYPE)
            #     if escape
            #     else ""
        )

    def visit_not_like_op_binary(self, binary, operator, **kw):
        # escape = binary.modifiers.get("escape", None)
        return "%s NOT LIKE %s" % (
            binary.left._compiler_dispatch(self, **kw),
            binary.right._compiler_dispatch(self, **kw),
            # ToDo - escape not yet supported
            # ) + (
            #     " ESCAPE " + self.render_literal_value(escape, sqltypes.STRINGTYPE)
            #     if escape
            #     else ""
        )

    def visit_merge(self, merge, **kw):
        clauses = "\n ".join(
            clause._compiler_dispatch(self, **kw) for clause in merge.clauses
        )
        source_kw = {"asfrom": True}
        if isinstance(merge.source, TableClause):
            source = (
                select(merge.source)
                .subquery()
                .alias(merge.source.name)
                ._compiler_dispatch(self, **source_kw)
            )
        elif isinstance(merge.source, Select):
            source = (
                merge.source.subquery()
                .alias(merge.source.get_final_froms()[0].name)
                ._compiler_dispatch(self, **source_kw)
            )
        elif isinstance(merge.source, Subquery):
            source = merge.source._compiler_dispatch(self, **source_kw)

        target_table = self.preparer.format_table(merge.target)
        return (
            f"MERGE INTO {target_table}\n"
            f" USING {source}\n"
            f" ON {merge.on}\n"
            f"{clauses if clauses else ''}"
        )

    def visit_when_merge_matched_update(self, merge_matched_update, **kw):
        case_predicate = (
            f" AND {str(merge_matched_update.predicate._compiler_dispatch(self, **kw))}"
            if merge_matched_update.predicate is not None
            else ""
        )
        update_str = f"WHEN MATCHED{case_predicate} THEN\n" f"\tUPDATE"
        if not merge_matched_update.set:
            return f"{update_str} *"

        set_list = list(merge_matched_update.set.items())
        if kw.get("deterministic", False):
            set_list.sort(key=operator.itemgetter(0))
        set_values = ", ".join(
            [
                f"{self.preparer.quote_identifier(set_item[0])} = {set_item[1]._compiler_dispatch(self, **kw)}"
                for set_item in set_list
            ]
        )
        return f"{update_str} SET {str(set_values)}"

    def visit_when_merge_matched_delete(self, merge_matched_delete, **kw):
        case_predicate = (
            f" AND {str(merge_matched_delete.predicate._compiler_dispatch(self, **kw))}"
            if merge_matched_delete.predicate is not None
            else ""
        )
        return f"WHEN MATCHED{case_predicate} THEN DELETE"

    def visit_when_merge_unmatched(self, merge_unmatched, **kw):
        case_predicate = (
            f" AND {str(merge_unmatched.predicate._compiler_dispatch(self, **kw))}"
            if merge_unmatched.predicate is not None
            else ""
        )
        insert_str = f"WHEN NOT MATCHED{case_predicate} THEN\n" f"\tINSERT"
        if not merge_unmatched.set:
            return f"{insert_str} *"

        set_cols, sets_vals = zip(*merge_unmatched.set.items())
        set_cols, sets_vals = list(set_cols), list(sets_vals)
        if kw.get("deterministic", False):
            set_cols, sets_vals = zip(
                *sorted(merge_unmatched.set.items(), key=operator.itemgetter(0))
            )
        return "{} ({}) VALUES ({})".format(
            insert_str,
            ", ".join(set_cols),
            ", ".join(map(lambda e: e._compiler_dispatch(self, **kw), sets_vals)),
        )


class DatabendExecutionContext(default.DefaultExecutionContext):
    @sa_util.memoized_property
    def should_autocommit(self):
        return False  # No DML supported, never autocommit

    def create_server_side_cursor(self):
        return self._dbapi_connection.cursor()

    def create_default_cursor(self):
        return self._dbapi_connection.cursor()


class DatabendTypeCompiler(compiler.GenericTypeCompiler):
    def visit_ARRAY(self, type_, **kw):
        return "Array(%s)" % type_

    def Visit_MAP(self, type_, **kw):
        return "Map(%s)" % type_

    def visit_NUMERIC(self, type_, **kw):
        if type_.precision is None:
            return self.visit_DECIMAL(sqltypes.DECIMAL(38, 10), **kw)
        if type_.scale is None:
            return self.visit_DECIMAL(sqltypes.DECIMAL(38, 10), **kw)
        return self.visit_DECIMAL(type_, **kw)

    def visit_NVARCHAR(self, type_, **kw):
        return self.visit_VARCHAR(type_, **kw)

    def visit_JSON(self, type_, **kw):
        return "JSON"  # or VARIANT

    def visit_TIME(self, type_, **kw):
        return "DATETIME"

    def visit_INTERVAL(self, type, **kw):
        return "INTERVAL"


class DatabendDDLCompiler(compiler.DDLCompiler):
    def visit_primary_key_constraint(self, constraint, **kw):
        return ""

    def visit_foreign_key_constraint(self, constraint, **kw):
        return ""

    def create_table_constraints(
        self, table, _include_foreign_key_constraints=None, **kw
    ):
        return ""

    def visit_create_index(
        self, create, include_schema=False, include_table_schema=True, **kw
    ):
        return ""

    def visit_drop_index(self, drop, **kw):
        return ""

    def visit_drop_schema(self, drop, **kw):
        # Override - Databend does not support the CASCADE option
        schema = self.preparer.format_schema(drop.element)
        return "DROP SCHEMA " + schema

    def visit_create_table(self, create, **kw):
        table = create.element
        db_opts = table.dialect_options["databend"]
        if "transient" in db_opts and db_opts["transient"]:
            if "transient" not in [p.lower() for p in table._prefixes]:
                table._prefixes.append("TRANSIENT")
        return super().visit_create_table(create, **kw)

    def post_create_table(self, table):
        table_opts = []
        db_opts = table.dialect_options["databend"]

        engine = db_opts.get("engine")
        if engine is not None:
            table_opts.append(f" ENGINE={engine}")

        cluster_keys = db_opts.get("cluster_by")
        if cluster_keys is not None:
            if isinstance(cluster_keys, str):
                cluster_by = cluster_keys
            elif isinstance(cluster_keys, list):
                cluster_by = ", ".join(
                    self.sql_compiler.process(
                        expr if not isinstance(expr, str) else table.c[expr],
                        include_table=False,
                        literal_binds=True,
                    )
                    for expr in cluster_keys
                )
            else:
                cluster_by = ""
            table_opts.append(f"\n CLUSTER BY ( {cluster_by} )")

        # ToDo - Engine options

        return " ".join(table_opts)


class DatabendDialect(default.DefaultDialect):
    name = "databend"
    driver = "databend"
    supports_cast = True
    supports_sane_rowcount = False
    supports_sane_multi_rowcount = False
    supports_native_boolean = True
    supports_native_decimal = True
    supports_alter = True
    supports_comments = False
    supports_empty_insert = False
    supports_is_distinct_from = False
    supports_multivalues_insert = True

    supports_statement_cache = False
    supports_server_side_cursors = True

    max_identifier_length = 127
    default_paramstyle = "pyformat"
    colspecs = colspecs
    ischema_names = ischema_names
    returns_native_bytes = True
    div_is_floordiv = False
    description_encoding = None
    postfetch_lastrowid = False

    preparer = DatabendIdentifierPreparer
    type_compiler = DatabendTypeCompiler
    statement_compiler = DatabendCompiler
    ddl_compiler = DatabendDDLCompiler
    execution_ctx_cls = DatabendExecutionContext

    # Required for PG-based compiler
    _backslash_escapes = True

    def __init__(
        self,
        context: Optional[ExecutionContext] = None,
        json_serializer=None,
        json_deserializer=None,
        *args: Any,
        **kwargs: Any,
    ):
        super(DatabendDialect, self).__init__(*args, **kwargs)
        self.context: Union[ExecutionContext, Dict] = context or {}
        self._json_serializer = json_serializer
        self._json_deserializer = json_deserializer

    @classmethod
    def dbapi(cls):
        return cls.import_dbapi()

    @classmethod
    def import_dbapi(cls):
        try:
            import databend_sqlalchemy.connector as connector
        except Exception:
            import connector
        return connector

    def _get_server_version_info(self, connection):
        val = connection.scalar(text("SELECT VERSION()"))
        m = re.match(r"(?:.*)v(\d+).(\d+).(\d+)-([^\(]+)(?:\()", val)
        if not m:
            raise AssertionError("Could not determine version from string '%s'" % val)
        return tuple(int(x) for x in m.group(1, 2, 3) if x is not None)

    def connect(self, *cargs, **cparams):
        # inherits the docstring from interfaces.Dialect.connect
        return self.dbapi.connect(*cargs, **cparams)

    def create_connect_args(self, url):
        parameters = dict(url.query)
        kwargs = {
            "dsn": "databend://%s:%s@%s:%d/%s"
            % (url.username, url.password, url.host, url.port or 8000, url.database),
        }

        if parameters:
            kwargs["dsn"] += "?"
            param_strings = []
            for k, v in parameters.items():
                param_strings.append(f"{k}={v}")
            kwargs["dsn"] += "&".join(param_strings)

        return ([], kwargs)

    def create_server_side_cursor(self):
        return self.create_default_cursor()

    def _get_default_schema_name(self, connection):
        return connection.scalar(text("SELECT currentDatabase()"))

    @reflection.cache
    def get_schema_names(self, connection, **kw):
        return [row[0] for row in connection.execute(text("SHOW DATABASES"))]

    def _get_table_columns(self, connection, table_name, schema):
        if schema is None:
            schema = self.default_schema_name
        quote_table_name = self.identifier_preparer.quote_identifier(table_name)
        quote_schema = self.identifier_preparer.quote_identifier(schema)

        return connection.execute(
            text(f"DESC {quote_schema}.{quote_table_name}")
        ).fetchall()

    @reflection.cache
    def has_table(self, connection, table_name, schema=None, **kw):
        if schema is None:
            schema = self.default_schema_name
        quote_table_name = self.identifier_preparer.quote_identifier(table_name)
        quote_schema = self.identifier_preparer.quote_identifier(schema)
        query = f"""EXISTS TABLE {quote_schema}.{quote_table_name}"""
        r = connection.scalar(text(query))
        if r == 1:
            return True
        return False

    @reflection.cache
    def get_columns(self, connection, table_name, schema=None, **kw):
        query = text(
            """
            select column_name, column_type, is_nullable
            from information_schema.columns
            where table_name = :table_name
            and table_schema = :schema_name
            """
        ).bindparams(
            bindparam("table_name", type_=sqltypes.UnicodeText),
            bindparam("schema_name", type_=sqltypes.Unicode),
        )
        if schema is None:
            schema = self.default_schema_name
        result = connection.execute(
            query, dict(table_name=table_name, schema_name=schema)
        )

        cols = [
            {
                "name": row[0],
                "type": self._get_column_type(row[1]),
                "nullable": get_is_nullable(row[2]),
                "default": None,
            }
            for row in result
        ]
        if not cols and not self.has_table(connection, table_name, schema):
            raise NoSuchTableError(table_name)
        return cols

    @reflection.cache
    def get_view_definition(self, connection, view_name, schema=None, **kw):
        if schema is None:
            schema = self.default_schema_name
        quote_schema = self.identifier_preparer.quote_identifier(schema)
        quote_view_name = self.identifier_preparer.quote_identifier(view_name)
        full_view_name = f"{quote_schema}.{quote_view_name}"

        # ToDo : perhaps can be removed if we get `SHOW CREATE VIEW`
        if view_name not in self.get_view_names(connection, schema):
            raise NoSuchTableError(full_view_name)

        query = f"""SHOW CREATE TABLE {full_view_name}"""
        try:
            view_def = connection.execute(text(query)).first()
            return view_def[1]
        except DBAPIError as e:
            if "1025" in e.orig.message:  # ToDo: The errors need parsing properly
                raise NoSuchTableError(full_view_name) from e

    def _get_column_type(self, column_type):
        pattern = r"(?:Nullable)*(?:\()*(\w+)(?:\((.*?)\))?(?:\))*"
        match = re.match(pattern, column_type)
        if match:
            type_str = match.group(1).lower()
            charlen = match.group(2)
            args = ()
            kwargs = {}
            if type_str == "decimal":
                if charlen:
                    # e.g.'18, 5'
                    prec, scale = charlen.split(", ")
                    args = (int(prec), int(scale))
            elif charlen:
                args = (int(charlen),)

            coltype = self.ischema_names[type_str]
            return coltype(*args, **kwargs)
        else:
            return None

    @reflection.cache
    def get_foreign_keys(self, connection, table_name, schema=None, **kw):
        # No support for foreign keys.
        return []

    @reflection.cache
    def get_pk_constraint(self, connection, table_name, schema=None, **kw):
        # No support for primary keys.
        return []

    @reflection.cache
    def get_indexes(self, connection, table_name, schema=None, **kw):
        return []

    @reflection.cache
    def get_table_names(self, connection, schema=None, **kw):
        table_name_query = """
            select table_name
            from information_schema.tables
            where table_schema = :schema_name
            and engine NOT LIKE '%VIEW%'
            """
        query = text(table_name_query).bindparams(
            bindparam("schema_name", type_=sqltypes.Unicode)
        )
        if schema is None:
            schema = self.default_schema_name

        result = connection.execute(query, dict(schema_name=schema))
        return [row[0] for row in result]

    @reflection.cache
    def get_view_names(self, connection, schema=None, **kw):
        view_name_query = """
            select table_name
            from information_schema.tables
            where table_schema = :schema_name
            and engine LIKE '%VIEW%'
        """
        # This handles bug that existed a while, views were not included in information_schema.tables
        # https://github.com/databendlabs/databend/issues/16039
        if self.server_version_info > (1, 2, 410) and self.server_version_info <= (
            1,
            2,
            566,
        ):
            view_name_query = """
                select table_name
                from information_schema.views
                where table_schema = :schema_name
                """
        query = text(view_name_query).bindparams(
            bindparam("schema_name", type_=sqltypes.Unicode)
        )
        if schema is None:
            schema = self.default_schema_name

        result = connection.execute(query, dict(schema_name=schema))
        return [row[0] for row in result]

    @reflection.cache
    def get_table_options(self, connection, table_name, schema=None, **kw):
        options = {}

        # transient??
        # engine: str
        # cluster_by: list[expr]
        # engine_options: dict

        # engine_regex = r'ENGINE=(\w+)'
        # cluster_key_regex = r'CLUSTER BY \((.*)\)'
        query_text = """
            SELECT engine_full, cluster_by, is_transient
            FROM system.tables
            WHERE database = :schema_name
            and name = :table_name
            """
        # This handles bug that existed a while
        # https://github.com/databendlabs/databend/pull/16149
        if self.server_version_info > (1, 2, 410) and self.server_version_info <= (
            1,
            2,
            604,
        ):
            query_text = """
                SELECT engine_full, cluster_by, is_transient
                FROM system.tables
                WHERE database = :schema_name
                and name = :table_name

                UNION

                SELECT engine_full, NULL as cluster_by, NULL as is_transient
                FROM system.views
                WHERE database = :schema_name
                and name = :table_name
                """
        query = text(query_text).bindparams(
            bindparam("table_name", type_=sqltypes.Unicode),
            bindparam("schema_name", type_=sqltypes.Unicode),
        )
        if schema is None:
            schema = self.default_schema_name

        result = connection.execute(
            query, dict(table_name=table_name, schema_name=schema)
        ).one_or_none()
        if not result:
            raise NoSuchTableError(
                f"{self.identifier_preparer.quote_identifier(schema)}."
                f"{self.identifier_preparer.quote_identifier(table_name)}"
            )

        if result.engine_full:
            options["databend_engine"] = result.engine_full
        if result.cluster_by:
            cluster_by = re.match(r"\((.*)\)", result.cluster_by).group(1)
            options["databend_cluster_by"] = cluster_by
        if result.is_transient:
            options["databend_is_transient"] = result.is_transient

        # engine options

        return options

    def do_rollback(self, dbapi_connection):
        # No transactions
        pass

    def _check_unicode_returns(self, connection, additional_tests=None):
        # We decode everything as UTF-8
        return True

    def _check_unicode_description(self, connection):
        # We decode everything as UTF-8
        return True


dialect = DatabendDialect


def get_is_nullable(column_is_nullable: str) -> bool:
    return column_is_nullable == "YES"


def extract_nullable_string(target):
    pattern = r"Nullable\((\w+)(?:\((.*?)\))?\)"
    if "Nullable" in target:
        match = re.match(pattern, target)
        if match:
            return match.group(1)
        else:
            return ""
    else:
        sl = target.split("(")
        if len(sl) > 0:
            return sl[0]
        return target
