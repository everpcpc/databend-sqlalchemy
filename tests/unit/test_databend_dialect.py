import os
from unittest import mock

import sqlalchemy
from conftest import MockCursor, MockDBApi
from pytest import mark
from sqlalchemy.engine import url
from sqlalchemy.sql import text

import databend_sqlalchemy  # SQLAlchemy package
from databend_sqlalchemy.databend_dialect import (
    DatabendCompiler,
    DatabendDialect,
    DatabendIdentifierPreparer,
    DatabendTypeCompiler,
    INTEGER, BOOLEAN, BINARY,
    DatabendDate
)
from databend_sqlalchemy.databend_dialect import dialect as dialect_definition


class TestDatabendDialect:
    def test_create_dialect(self, dialect: DatabendDialect):
        assert issubclass(dialect_definition, DatabendDialect)
        assert isinstance(DatabendDialect.dbapi(), type(databend_sqlalchemy))
        assert dialect.name == "databend"
        assert dialect.driver == "databend"
        assert issubclass(dialect.preparer, DatabendIdentifierPreparer)
        assert issubclass(dialect.statement_compiler, DatabendCompiler)
        # SQLAlchemy's DefaultDialect creates an instance of
        # type_compiler behind the scenes
        assert isinstance(dialect.type_compiler, DatabendTypeCompiler)
        assert dialect.context == {}

    def test_create_connect_args(self, dialect: DatabendDialect):
        u = url.make_url("databend://user:pass@localhost:8000/testdb")
        result_list, result_dict = dialect.create_connect_args(u)
        assert result_dict["dsn"] == "databend://user:pass@localhost:8000/testdb"

        u = url.make_url("databend://user:pass@host:443/db")
        args, kwargs = dialect.create_connect_args(u)
        assert args == []
        assert kwargs["dsn"] == "databend://user:pass@host:443/db"

        u = url.make_url("databend://user:pass@host:443/db?warehouse=test&secure=True")
        args, kwargs = dialect.create_connect_args(u)
        assert args == []
        assert kwargs["dsn"] == "databend://user:pass@host:443/db?warehouse=test&secure=True"

    def test_do_execute(
            self, dialect: DatabendDialect, cursor: mock.Mock(spec=MockCursor)
    ):
        dialect.do_execute(cursor, "SELECT *", None)
        cursor.execute.assert_called_once_with("SELECT *", None)
        cursor.execute.reset_mock()
        dialect.do_execute(cursor, "SELECT *", (1, 22), None)

    def test_table_names(
            self, dialect: DatabendDialect, connection: mock.Mock(spec=MockDBApi)
    ):
        connection.execute.return_value = [
            ("table1",),
            ("table2",),
        ]

        result = dialect.get_table_names(connection)
        assert result == ["table1", "table2"]
        connection.execute.assert_called_once()
        assert str(connection.execute.call_args[0][0].compile()) == str(
            text("""
            select table_name
            from information_schema.tables
            where table_schema = :schema_name
            and engine NOT LIKE '%VIEW%'
            """).compile()
        )
        assert connection.execute.call_args[0][1] == {'schema_name': None}
        connection.execute.reset_mock()
        # Test default schema
        dialect.default_schema_name = 'some-schema'
        result = dialect.get_table_names(connection)
        assert result == ["table1", "table2"]
        connection.execute.assert_called_once()
        assert str(connection.execute.call_args[0][0].compile()) == str(
            text("""
            select table_name
            from information_schema.tables
            where table_schema = :schema_name
            and engine NOT LIKE '%VIEW%'
            """).compile()
        )
        assert connection.execute.call_args[0][1] == {'schema_name': 'some-schema'}
        connection.execute.reset_mock()
        # Test specified schema
        result = dialect.get_table_names(connection, schema="schema")
        assert result == ["table1", "table2"]
        connection.execute.assert_called_once()
        assert str(connection.execute.call_args[0][0].compile()) == str(
            text("""
            select table_name
            from information_schema.tables
            where table_schema = :schema_name
            and engine NOT LIKE '%VIEW%'
            """).compile()
        )
        assert connection.execute.call_args[0][1] == {'schema_name': 'schema'}

    def test_view_names(
            self, dialect: DatabendDialect, connection: mock.Mock(spec=MockDBApi)
    ):
        connection.execute.return_value = []
        assert dialect.get_view_names(connection) == []

    def test_indexes(
            self, dialect: DatabendDialect, connection: mock.Mock(spec=MockDBApi)
    ):
        assert dialect.get_indexes(connection, "table") == []

    def test_columns(
            self, dialect: DatabendDialect, connection: mock.Mock(spec=MockDBApi)
    ):
        def multi_column_row(columns):
            def getitem(self, idx):
                for i, result in enumerate(columns):
                    if idx == i:
                        return result

            return mock.Mock(__getitem__=getitem)

        connection.execute.return_value = [
            multi_column_row(["name1", "INT", "YES"]),
            multi_column_row(["name2", "date", "NO"]),
            multi_column_row(["name3", "boolean", "YES"]),
            multi_column_row(["name4", "binary", "YES"])
        ]

        expected_query = """
            select column_name, column_type, is_nullable
            from information_schema.columns
            where table_name = :table_name
            and table_schema = :schema_name
            """

        for call, expected_params in (
                (
                        lambda: dialect.get_columns(connection, "table"),
                        {'table_name': 'table', 'schema_name': None},
                ),
                (
                        lambda: dialect.get_columns(connection, "table", "schema"),
                        {'table_name': 'table', 'schema_name': 'schema'},
                ),
        ):
            result = call()
            assert result == [
                {
                    "name": "name1",
                    "type": INTEGER,
                    "nullable": True,
                    "default": None,
                },
                {
                    "name": "name2",
                    "type": DatabendDate,
                    "nullable": False,
                    "default": None,
                },
                {
                    "name": "name3",
                    "type": BOOLEAN,
                    "nullable": True,
                    "default": None,
                },
                {
                    "name": "name4",
                    "type": BINARY,
                    "nullable": True,
                    "default": None,
                },
            ]
            connection.execute.assert_called_once()
            assert str(connection.execute.call_args[0][0].compile()) == str(
                text(expected_query).compile()
            )
            assert connection.execute.call_args[0][1] == expected_params
            connection.execute.reset_mock()


def test_get_is_nullable():
    assert databend_sqlalchemy.databend_dialect.get_is_nullable("YES")
    assert not databend_sqlalchemy.databend_dialect.get_is_nullable("NO")


def test_types():
    assert databend_sqlalchemy.databend_dialect.CHAR is sqlalchemy.sql.sqltypes.CHAR
    assert issubclass(databend_sqlalchemy.databend_dialect.DatabendDate, sqlalchemy.sql.sqltypes.DATE)
    assert issubclass(
        databend_sqlalchemy.databend_dialect.DatabendDateTime,
        sqlalchemy.sql.sqltypes.DATETIME,
    )
    assert (
            databend_sqlalchemy.databend_dialect.INTEGER is sqlalchemy.sql.sqltypes.INTEGER
    )
    assert databend_sqlalchemy.databend_dialect.BIGINT is sqlalchemy.sql.sqltypes.BIGINT
    assert (
            databend_sqlalchemy.databend_dialect.TIMESTAMP
            is sqlalchemy.sql.sqltypes.TIMESTAMP
    )
    assert (
            databend_sqlalchemy.databend_dialect.VARCHAR is sqlalchemy.sql.sqltypes.VARCHAR
    )
    assert (
            databend_sqlalchemy.databend_dialect.BOOLEAN is sqlalchemy.sql.sqltypes.BOOLEAN
    )
    assert databend_sqlalchemy.databend_dialect.FLOAT is sqlalchemy.sql.sqltypes.FLOAT
    assert issubclass(
        databend_sqlalchemy.databend_dialect.ARRAY, sqlalchemy.types.TypeEngine
    )


def test_extract_nullable_string():
    types = ["INT", "FLOAT", "Nullable(INT)", "Nullable(Decimal(2,4))", "Nullable(Array(INT))",
             "Nullable(Map(String, String))", "Decimal(1,2)"]
    expected_types = ["int", "float", "int", "decimal", "array", "map", "decimal"]
    i = 0
    for t in types:
        true_type = databend_sqlalchemy.databend_dialect.extract_nullable_string(t).lower()
        assert expected_types[i] == true_type
        i += 1
        print(true_type)
