package com.synapcore.companion

import android.annotation.SuppressLint
import android.app.Activity
import android.bluetooth.*
import android.bluetooth.le.*
import android.content.*
import android.graphics.*
import android.graphics.drawable.GradientDrawable
import android.media.Ringtone
import android.media.RingtoneManager
import android.net.Uri
import android.os.*
import android.provider.ContactsContract
import android.telecom.TelecomManager
import android.telephony.TelephonyManager
import android.util.Log
import android.view.Gravity
import android.widget.*
import java.util.Locale

@SuppressLint("MissingPermission")
class MainActivity : Activity() {
    private var gatt: BluetoothGatt? = null
    private val canais = ArrayList<BluetoothGattCharacteristic>()
    private val MAC = "00:00:00:00:00:00"
    private lateinit var consoleLog: TextView
    private lateinit var b3: Button; private lateinit var b4: Button; private lateinit var b5: Button
    private var ultimoNum = "5511900000000"; private var ultimoNome = "CHAMADA"
    private var toque: Ringtone? = null; private var escaneando = false
    private var pacotePendente: ByteArray? = null
    private val h = Handler(Looper.getMainLooper())

    private val rec = object : BroadcastReceiver() {
        override fun onReceive(c: Context, i: Intent) {
            try {
                val st = i.getStringExtra(TelephonyManager.EXTRA_STATE)
                val n = i.getStringExtra(TelephonyManager.EXTRA_INCOMING_NUMBER)
                if (TelephonyManager.EXTRA_STATE_RINGING == st) {
                    if (!n.isNullOrEmpty()) {
                        ultimoNum = n.replace("[^0-9]".toRegex(), "")
                        ultimoNome = nomeContato(n) ?: n
                    }
                    atuBotoes()
                    log("CHAMADA DE: " + ultimoNome + " (" + ultimoNum + ")")
                    enviar("645_OK", hex("7e6d034d0087753702081310001887efc4d706ba0134080f1008181a22002a085768617473417070321a50726f637572616e646f206e6f766173206d656e736167656e733887efc4d706e802d4fdffffffffffffff01"))
                }
            } catch (e: Exception) {}
        }
    }

    private val alertaKaliRec = object : BroadcastReceiver() {
        override fun onReceive(c: Context, i: Intent) {
            ultimoNome = (i.getStringExtra("titulo") ?: "INVASAO!").take(8).toUpperCase(Locale.ROOT)
            ultimoNum = (i.getStringExtra("mensagem") ?: "ALERTA KALI").take(26).toUpperCase(Locale.ROOT)
            atuBotoes()
            log("ALERTA KALI: " + ultimoNome + " | " + ultimoNum)
            enviar("645_OK", hex("7e6d034d0087753702081310001887efc4d706ba0134080f1008181a22002a085768617473417070321a50726f637572616e646f206e6f766173206d656e736167656e733887efc4d706e802d4fdffffffffffffff01"))
        }
    }

    override fun onCreate(s: Bundle?) {
        super.onCreate(s)
        val rb = GradientDrawable().apply { setColor(Color.parseColor("#000000")); setStroke(6, Color.parseColor("#80FF00")) }
        val lay = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL; background = rb; setPadding(26, 26, 26, 26) }
        val tit = TextView(this).apply { text = "SYNAPCORE // SENTINEL & WATCH [OK]"; setTextColor(Color.parseColor("#80FF00")); textSize = 14f; typeface = Typeface.MONOSPACE; gravity = Gravity.CENTER; setPadding(0, 0, 0, 16) }
        fun btn(t: String, cor: String, ac: () -> Unit) = Button(this).apply {
            text = t; setTextColor(Color.parseColor("#80FF00")); textSize = 11f; typeface = Typeface.MONOSPACE
            background = GradientDrawable().apply { setColor(Color.parseColor("#030604")); setStroke(4, Color.parseColor(cor)); cornerRadius = 8f }
            layoutParams = LinearLayout.LayoutParams(-1, -2).apply { setMargins(0, 0, 0, 12) }; setOnClickListener { ac() }
        }
        val b1 = btn("[ 1. CONECTAR + DESTRAVAR MTU ]", "#80FF00") { conectar() }
        val b2 = btn("[ 2. VIBRAR: ALERTA WHATSAPP (645 OK) ]", "#FF006A") { enviar("645_OK", hex("7e6d034d0087753702081310001887efc4d706ba0134080f1008181a22002a085768617473417070321a50726f637572616e646f206e6f766173206d656e736167656e733887efc4d706e802d4fdffffffffffffff01")) }
        b3 = btn("[ 3. TOCAR + CHAMAR: " + ultimoNome + " (" + ultimoNum + ") ]", "#FF006A") { enviar("645_OK", hex("7e6d034d0087753702081310001887efc4d706ba0134080f1008181a22002a085768617473417070321a50726f637572616e646f206e6f766173206d656e736167656e733887efc4d706e802d4fdffffffffffffff01")) }
        b4 = btn("[ 4. ATENDER / PARAR SOM: " + ultimoNome + " ]", "#80FF00") { atender() }
        b5 = btn("[ 5. MANDAR WHATSAPP P/: " + ultimoNum + " ]", "#FF006A") { abrirWhats() }
        consoleLog = TextView(this).apply { text = "> MODO SENTINELA ATIVO! Aguardando Kali ou Botao 1."; setTextColor(Color.parseColor("#FF006A")); textSize = 11f; typeface = Typeface.MONOSPACE; setPadding(16, 16, 16, 16) }
        val sc = ScrollView(this).apply { background = GradientDrawable().apply { setColor(Color.parseColor("#050002")); setStroke(3, Color.parseColor("#80FF00")) }; layoutParams = LinearLayout.LayoutParams(-1, -1); addView(consoleLog) }
        lay.addView(tit); lay.addView(b1); lay.addView(b2); lay.addView(b3); lay.addView(b4); lay.addView(b5); lay.addView(sc); setContentView(lay)
        try {
            val fl = IntentFilter(TelephonyManager.ACTION_PHONE_STATE_CHANGED)
            val flKali = IntentFilter("com.synapcore.ALERTA_INVASAO")
            if (Build.VERSION.SDK_INT >= 33) {
                registerReceiver(rec, fl, Context.RECEIVER_EXPORTED)
                registerReceiver(alertaKaliRec, flKali, Context.RECEIVER_EXPORTED)
            } else {
                registerReceiver(rec, fl)
                registerReceiver(alertaKaliRec, flKali)
            }
        } catch (e: Exception) {}
    }

    private fun atuBotoes() {
        runOnUiThread {
            b3.text = "[ 3. TOCAR + CHAMAR: " + ultimoNome + " (" + ultimoNum + ") ]"
            b4.text = "[ 4. ATENDER / PARAR SOM: " + ultimoNome + " ]"
            b5.text = "[ 5. MANDAR WHATSAPP P/: " + ultimoNum + " ]"
        }
    }

    private fun dispararChamadaClonada645() {
        try {
            toque?.stop()
            val u = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE)
            toque = RingtoneManager.getRingtone(applicationContext, u)
            toque?.play()
            log("TOCANDO SOM NO ANDROID!")
        } catch (e: Exception) {}
        val pkt = hex("7e6d034d0087753702081310001887efc4d706ba0134080f1008181a22002a085768617473417070321a50726f637572616e646f206e6f766173206d656e736167656e733887efc4d706e802d4fdffffffffffffff01")
        val tit = (ultimoNome + "        ").substring(0, 8).toByteArray(Charsets.US_ASCII)
        for (i in 0 until 8) pkt.set(31 + i, tit.get(i))
        val msg = ("LIGACAO: " + ultimoNum + "              ").substring(0, 26).toByteArray(Charsets.US_ASCII)
        for (i in 0 until 26) pkt.set(41 + i, msg.get(i))
        var crc = 0
        for (i in 7 until pkt.size) {
            crc = crc xor (pkt.get(i).toInt() and 0xFF)
            for (b in 0 until 8) crc = if ((crc and 1) != 0) (crc shr 1) xor 0xA001 else (crc shr 1)
        }
        pkt.set(5, (crc and 0xFF).toByte())
        pkt.set(6, ((crc shr 8) and 0xFF).toByte())
        enviar("CHAMADA_645", pkt)
    }

    private fun nomeContato(n: String): String? {
        try {
            val u = Uri.withAppendedPath(ContactsContract.PhoneLookup.CONTENT_FILTER_URI, Uri.encode(n))
            contentResolver.query(u, arrayOf(ContactsContract.PhoneLookup.DISPLAY_NAME), null, null, null)?.use {
                if (it.moveToFirst()) return it.getString(0)
            }
        } catch (e: Exception) {}
        return null
    }

    private fun atender() {
        toque?.stop()
        try { (getSystemService(TELECOM_SERVICE) as TelecomManager).acceptRingingCall() } catch (e: Exception) {}
        log("TOQUE PARADO!")
    }

    private fun abrirWhats() {
        toque?.stop()
        try {
            val u = Uri.Builder().scheme("https").authority("://whatsapp.com").path("send")
                .appendQueryParameter("phone", ultimoNum)
                .appendQueryParameter("text", "Estou no laboratorio Synapcore, ja te retorno!").build()
            val i = Intent(Intent.ACTION_VIEW, u)
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            startActivity(i)
        } catch (e: Exception) {}
    }

    private fun log(m: String) {
        Log.i("SYNAPCORE_LAB", m)
        runOnUiThread { consoleLog.append(System.lineSeparator() + "> " + m) }
    }

    private fun hex(s: String) = ByteArray(s.length / 2) { ((Character.digit(s.get(it * 2), 16) shl 4) + Character.digit(s.get(it * 2 + 1), 16)).toByte() }

    private fun conectar() {
        val ad = BluetoothAdapter.getDefaultAdapter()
        val bm = getSystemService(BLUETOOTH_SERVICE) as BluetoothManager
        for (d in bm.getConnectedDevices(BluetoothProfile.GATT)) if (d.address.equals(MAC, true)) { abrirGatt(d); return }
        val sc = ad.bluetoothLeScanner
        if (escaneando) return
        escaneando = true
        log("Buscando relogio 3s...")
        sc?.startScan(null, ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(), cbScan)
        h.postDelayed({
            if (escaneando) {
                escaneando = false
                sc?.stopScan(cbScan)
                abrirGatt(ad.getRemoteDevice(MAC))
            }
        }, 3000)
    }

    private val cbScan = object : ScanCallback() {
        override fun onScanResult(t: Int, r: ScanResult) {
            if (r.device.address.equals(MAC, true) && escaneando) {
                escaneando = false
                BluetoothAdapter.getDefaultAdapter().bluetoothLeScanner?.stopScan(this)
                abrirGatt(r.device)
            }
        }
    }

    private fun abrirGatt(d: BluetoothDevice) {
        gatt?.close()
        gatt = d.connectGatt(this, false, cbGatt, BluetoothDevice.TRANSPORT_LE)
    }

    private val cbGatt = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(g: BluetoothGatt, s: Int, st: Int) {
            if (st == 2) {
                log("CONECTADO! MTU 247...")
                g.requestMtu(247)
            } else if (st == 0) {
                log("Desconectado ($s)")
                g.close()
                gatt = null
                canais.clear()
            }
        }
        override fun onMtuChanged(g: BluetoothGatt, mtu: Int, s: Int) { g.discoverServices() }
        override fun onServicesDiscovered(g: BluetoothGatt, s: Int) {
            canais.clear()
            for (sv in g.services) for (c in sv.characteristics) if ((c.properties and 12) != 0) canais.add(c)
            log("PRONTO! " + canais.size + " portas abertas.")
            pacotePendente?.let { p ->
                pacotePendente = null
                enviar("AUTO_ALERTA_KALI", p)
            }
        }
    }

    private fun enviar(n: String, b: ByteArray) {
        val g = gatt
        if (g == null || canais.isEmpty()) {
            log("Relogio desconectado! Reconectando para enviar $n...")
            pacotePendente = b
            conectar()
            return
        }
        canais.forEachIndexed { i, c ->
            h.postDelayed({
                c.value = b
                c.writeType = 1
                val ok = g.writeCharacteristic(c)
                log(n + " -> " + c.uuid.toString().substring(0, 8) + ": " + ok)
            }, (i * 150).toLong())
        }
    }
}
