// import { useState } from 'react'
import './App.css'
import { Routes, Route } from 'react-router'
import FirmwareList from './pages/FirmwareList';
import FirmwareUpload from './pages/FirmwareUpload';

function App() {
  return (
    <>
      <Routes>
        <Route index element={<FirmwareList />} />
        <Route path="/upload" element={<FirmwareUpload />} />
      </Routes>
    </>
  )
}

export default App
