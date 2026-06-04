if(NOT DEFINED EXPORTER)
    message(FATAL_ERROR "EXPORTER is required")
endif()
if(NOT DEFINED ARG_NAME)
    message(FATAL_ERROR "ARG_NAME is required")
endif()
if(NOT DEFINED ARG_VALUE)
    message(FATAL_ERROR "ARG_VALUE is required")
endif()
if(NOT DEFINED EXPECTED_TEXT)
    message(FATAL_ERROR "EXPECTED_TEXT is required")
endif()

execute_process(
    COMMAND "${EXPORTER}" "${ARG_NAME}" "${ARG_VALUE}"
    RESULT_VARIABLE result
    OUTPUT_VARIABLE stdout
    ERROR_VARIABLE stderr
)

if(result EQUAL 0)
    message(FATAL_ERROR "Exporter accepted invalid input: ${ARG_NAME} ${ARG_VALUE}")
endif()

set(combined_output "${stdout}\n${stderr}")
string(FIND "${combined_output}" "${EXPECTED_TEXT}" found_at)
if(found_at EQUAL -1)
    message(FATAL_ERROR
        "Exporter failed for the wrong reason. Expected text: ${EXPECTED_TEXT}\n${combined_output}"
    )
endif()
