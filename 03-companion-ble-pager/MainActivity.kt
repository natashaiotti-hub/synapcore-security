package com.synapcore.companion
import android.annotation.SuppressLint
import android.app.Activity
import android.bluetooth.*
import android.bluetooth.le.*
import android.content.*
import android.graphics.*
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.*
import android.provider.ContactsContract
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
    private lateinit var b2: Button
    private lateinit var b3: Button
    private var ultimoNum = "5511900000000"
    private var ultimoNome = "SYNAPCORE"
    private var ultimoTexto = "PRONTO"
    private var escaneando = false
    private var pacotePendente: ByteArray? = null
    private val h = Handler(Looper.getMainLooper())

    private val PKT_VIBRAR_645 = "7e6d034d0087753702081310001887efc4d706ba0134080f1008181a22002a085768617473417070321a50726f637572616e646f206e6f766173206d656e736167656e733887efc4d706e802d4fdffffffffffffff01"

    private val rec = object : BroadcastReceiver() {
        override fun onReceive(c: Context, i: Intent) {
            try {
                val st = i.getStringExtra(TelephonyManager.EXTRA_STATE)
                val n = i.getStringExtra(TelephonyManager.EXTRA_INCOMING_NUMBER)
                if (TelephonyManager.EXTRA_STATE_RINGING == st) {
                    if (!n.isNullOrEmpty()) {
                        ultimoNum = n.replace("[^0-9]".toRegex(), "")
                        ultimoNome = nomeContato(n) ?: "CHAMADA"
                    }
                    ultimoTexto = ultimoNum
                    atuBotoes()
                    log("RECEBIDO DE: " + ultimoNome + " (" + ultimoNum + ")")
                    enviar("645_OK", hex(PKT_VIBRAR_645))
                }
            } catch (e: Exception) {}
        }
    }

    private val alertaKaliRec = object : BroadcastReceiver() {
        override fun onReceive(c: Context, i: Intent) {
            ultimoNome = (i.getStringExtra("titulo") ?: "INVASAO!").take(12).toUpperCase(Locale.ROOT)
            ultimoTexto = (i.getStringExtra("mensagem") ?: "ALERTA KALI").take(26).toUpperCase(Locale.ROOT)
            atuBotoes()
            log("ALARME KALI: " + ultimoNome + " | " + ultimoTexto)
            enviar("645_OK", hex(PKT_VIBRAR_645))
        }
    }

    override fun onCreate(s: Bundle?) {
        super.onCreate(s)
        val rb = GradientDrawable().apply { setColor(Color.parseColor("#000000")); setStroke(6, Color.parseColor("#80FF00")) }
        val lay = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL; background = rb; setPadding(26, 26, 26, 26) }
        val tit = TextView(this).apply { text = "SYNAPCORE // SENTINEL & WATCH [OK]"; setTextColor(Color.parseColor("#80FF00")); textSize = 14f; typeface = Typeface.MONOSPACE; gravity = Gravity.CENTER; setPadding(0, 0, 0, 18) }

        fun btn(t: String, cor: String, ac: () -> Unit) = Button(this).apply {
            text = t; setTextColor(Color.parseColor("#80FF00")); textSize = 11f; typeface = Typeface.MONOSPACE
            background = GradientDrawable().apply { setColor(Color.parseColor("#030604")); setStroke(4, Color.parseColor(cor)); cornerRadius = 8f }
            layoutParams = LinearLayout.LayoutParams(-1, -2).apply { setMargins(0, 0, 0, 14) }; setOnClickListener { ac() }
        }

        val b1 = btn("[ 1. CONECTAR + DESTRAVAR MTU ]", "#80FF00") { conectar() }
        b2 = btn("[ 2. VIBRAR ALERTA (645 OK): " + ultimoNome + " ]", "#FF006A") { enviar("645_OK", hex(PKT_VIBRAR_645)) }
        b3 = btn("[ 3. MANDAR WHATSAPP P/: " + ultimoNum + " ]", "#80FF00") { abrirWhats() }

        consoleLog = TextView(this).apply { text = "> MODO SENTINELA ATIVO! Aguardando Alarme Kali ou WhatsApp."; setTextColor(Color.parseColor("#FF006A")); textSize = 11f; typeface = Typeface.MONOSPACE; setPadding(16, 16, 16, 16) }
        val sc = ScrollView(this).apply { background = GradientDrawable().apply { setColor(Color.parseColor("#050002")); setStroke(3, Color.parseColor("#80FF00")) }; layoutParams = LinearLayout.LayoutParams(-1, -1); addView(consoleLog) }

        lay.addView(tit); lay.addView(b1); lay.addView(b2); lay.addView(b3); lay.addView(sc); setContentView(lay)

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
            b2.text = "[ 2. VIBRAR ALERTA (645 OK): " + ultimoNome + " | " + ultimoTexto + " ]"
            b3.text = "[ 3. MANDAR WHATSAPP P/: " + ultimoNum + " ]"
        }
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

    private fun abrirWhats() {
        try {
            val u = Uri.Builder().scheme("https").authority("api.whatsapp.com").path("send")
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
