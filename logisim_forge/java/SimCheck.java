import com.cburch.logisim.file.*;
import com.cburch.logisim.circuit.*;
import com.cburch.logisim.comp.*;
import com.cburch.logisim.data.*;
import com.cburch.logisim.instance.*;
import com.cburch.logisim.std.wiring.Pin;
import com.cburch.logisim.proj.Project;
import java.io.*;
import java.nio.file.*;
import java.awt.*;
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;
import java.util.*;

/** Runs real Logisim propagation; CSV columns are pin labels, input or output.
 * Outputs are checked against independent vectors. Never evaluates gate logic here.
 */
public class SimCheck {
  static class StrictLoader extends Loader {
    StrictLoader(){super(null);}
    public void showError(String s){throw new IllegalArgumentException("LOADER ERROR: "+s);}
  }
  static void render(Circuit c, CircuitState st, String path) throws Exception {
    BufferedImage probe=new BufferedImage(1,1,BufferedImage.TYPE_INT_RGB);
    Graphics2D pg=probe.createGraphics(); Bounds b=c.getBounds(pg); pg.dispose();
    int pad=50, scale=2;
    BufferedImage im=new BufferedImage((b.getWidth()+2*pad)*scale,(b.getHeight()+2*pad)*scale,BufferedImage.TYPE_INT_RGB);
    Graphics2D g=im.createGraphics();g.setColor(Color.WHITE);g.fillRect(0,0,im.getWidth(),im.getHeight());
    g.setColor(Color.BLACK);g.scale(scale,scale);g.translate(pad-b.getX(),pad-b.getY());
    g.setRenderingHint(RenderingHints.KEY_ANTIALIASING,RenderingHints.VALUE_ANTIALIAS_ON);
    ComponentDrawContext ctx=new ComponentDrawContext(new javax.swing.JPanel(),c,st,g,g);
    ctx.setShowState(true);ctx.setShowColor(true);c.draw(ctx,Collections.emptySet());g.dispose();
    ImageIO.write(im,"png",new File(path));
  }
  public static void main(String[] args) {
    try {run(args);System.exit(0);} catch(Throwable t){t.printStackTrace();System.exit(1);}
  }
  static void run(String[] args) throws Exception {
    LogisimFile f=new StrictLoader().openLogisimFile(new File(args[0]));
    if(f==null)throw new IllegalArgumentException("null project");
    Circuit c=null;for(Circuit cc:f.getCircuits())if(cc.getName().equals(args[1]))c=cc;
    if(c==null)throw new IllegalArgumentException("unknown circuit "+args[1]);
    Project p=new Project(f);CircuitState st=new CircuitState(p,c);
    Map<String,com.cburch.logisim.comp.Component> pins=new LinkedHashMap<>();
    for(com.cburch.logisim.comp.Component co:c.getNonWires()) if(co.getFactory() instanceof Pin){
      String label=co.getAttributeSet().getValue(StdAttr.LABEL);
      if(pins.put(label,co)!=null)throw new IllegalArgumentException("duplicate pin label "+label);
    }
    java.util.List<String> lines=Files.readAllLines(Path.of(args[2]));
    if(lines.isEmpty())throw new IllegalArgumentException("CSV must contain a header and at least one data row");
    String[] headers=lines.get(0).trim().isEmpty()?new String[0]:lines.get(0).trim().split(",");
    if(new HashSet<>(Arrays.asList(headers)).size()!=headers.length)throw new IllegalArgumentException("duplicate CSV column");
    Set<String> seen=new HashSet<>(); for(String h:headers)if(!h.startsWith("@"))seen.add(h);
    if(!seen.equals(pins.keySet()))throw new IllegalArgumentException("vector headers differ from pins: "+pins.keySet());
    System.out.println(String.join(",",headers)+",PASS");int count=0;
    for(int row=1;row<lines.size();row++){
      if(lines.get(row).trim().isEmpty())continue;
      String[] vals=lines.get(row).trim().split(",");
      if(vals.length!=headers.length)throw new IllegalArgumentException("row "+row+" has "+vals.length+" values, expected "+headers.length);
      for(int i=0;i<headers.length;i++){
        if(headers[i].startsWith("@"))continue;
        com.cburch.logisim.comp.Component co=pins.get(headers[i]);
        if(Pin.FACTORY.isInputPin(Instance.getInstanceFor(co))){
          Pin.FACTORY.setValue(st.getInstanceState(co),Value.createKnown(co.getEnd(0).getWidth(),parseValue(vals[i],co.getEnd(0).getWidth().getWidth())));
          st.markComponentAsDirty(co);
        }
      }
      st.getPropagator().propagate();
      if(st.getPropagator().isOscillating())throw new IllegalStateException("oscillation");
      if(c.getWidthIncompatibilityData()!=null&&!c.getWidthIncompatibilityData().isEmpty())throw new IllegalStateException("width mismatch");
      boolean ok=true;StringJoiner actual=new StringJoiner(",");
      for(int i=0;i<headers.length;i++){
        Value v;
        if(headers[i].startsWith("@")){
          String[] xy=headers[i].substring(1).split(":");
          v=st.getValue(Location.create(Integer.parseInt(xy[0]),Integer.parseInt(xy[1])));
        } else {
          com.cburch.logisim.comp.Component co=pins.get(headers[i]);
          v=Pin.FACTORY.getValue(st.getInstanceState(co));
        }
        actual.add(v.isFullyDefined()?""+v.toIntValue():v.toDisplayString());
        if(!v.isFullyDefined()||v.toIntValue()!=parseValue(vals[i],v.getWidth()))ok=false;
      }
      System.out.println(actual+","+ok);
      if(!ok)throw new IllegalStateException("row "+row+" expected "+lines.get(row)+" got "+actual);
      audit(st);
      count++;
    }
    if(count==0)throw new IllegalArgumentException("CSV must contain at least one data row");
    st.getPropagator().propagate();
    // Inspect all connected component ports, including displays and subcircuits.
    audit(st);
    if(args.length>3)render(c,st,args[3]);
    System.err.println("PASS "+c.getName()+" rows="+count+"; connected ports defined; widths valid");
  }
  static void audit(CircuitState st){
    if(st.getCircuit().getWidthIncompatibilityData()!=null&&!st.getCircuit().getWidthIncompatibilityData().isEmpty())throw new IllegalStateException("width mismatch in "+st.getCircuit().getName());
    for(com.cburch.logisim.comp.Component co:st.getCircuit().getNonWires())for(EndData e:co.getEnds()){
      // Unconnected ports can have legitimate component defaults (for example,
      // a disabled optional enable pin). Check only electrically connected ends.
      if(!st.getCircuit().isConnected(e.getLocation(),co))continue;
      Value v=st.getValue(e.getLocation());
      if(!v.isFullyDefined())throw new IllegalStateException("undefined port "+co.getFactory().getName()+" "+e.getLocation()+"="+v);
    }
    for(CircuitState sub:st.getSubstates())audit(sub);
  }
  static int parseValue(String text,int width){
    long n=Long.parseLong(text.trim());
    long min=width==32?Integer.MIN_VALUE:0;
    long max=(1L<<width)-1;
    if(width<1 || width>32 || n<min || n>max)throw new IllegalArgumentException("value "+text+" outside "+width+"-bit range");
    return (int)n;
  }
}
