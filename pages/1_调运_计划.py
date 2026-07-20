"""调运 — 计划模块"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from pages._transport_page import render_transport_page

st.set_page_config(page_title="调运 - 计划", page_icon="📋", layout="wide")
render_transport_page("计划")
